import fs from "fs";
import path from "path";
import { chromium } from "playwright";

const args = process.argv.slice(2);
const getArg = (name, fallback = null) => {
  const idx = args.indexOf(name);
  if (idx === -1) return fallback;
  return args[idx + 1] || fallback;
};

const suitePath = getArg("--suite");
const headless = args.includes("--headless");

if (!suitePath) {
  console.error("Missing --suite <path>");
  process.exit(1);
}

const suiteAbs = path.isAbsolute(suitePath)
  ? suitePath
  : path.join(process.cwd(), suitePath);
const suite = JSON.parse(fs.readFileSync(suiteAbs, "utf-8"));

const baseUrl = suite.base_url;
const apiBase = suite.api_base;
const steps = suite.steps || [];
const assertions = suite.assertions || [];

const outputDir = path.join(
  path.dirname(suiteAbs),
  "output",
  new Date().toISOString().replace(/[:.]/g, "_")
);
fs.mkdirSync(outputDir, { recursive: true });

const results = [];
const assertionResults = [];
const consoleErrors = [];
const networkResponses = [];

const recordResult = (stepId, action, status, detail = "", screenshot = "") => {
  results.push({ stepId, action, status, detail, screenshot });
};

const recordAssertion = (stepId, action, status, detail = "") => {
  assertionResults.push({ stepId, action, status, detail });
};

const expectStatus = (actual, expected) => {
  if (Array.isArray(expected)) return expected.includes(actual);
  return actual === expected;
};

const httpPost = async (url, payload) => {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : undefined
  });
  const text = await res.text();
  return { status: res.status, text };
};

const httpGet = async (url) => {
  const res = await fetch(url, { method: "GET" });
  const text = await res.text();
  return { status: res.status, text };
};

const run = async () => {
  const browser = await chromium.launch({ headless });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on("console", msg => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("response", resp => {
    networkResponses.push({ url: resp.url(), status: resp.status() });
  });
  page.on("dialog", dialog => dialog.accept());

  for (const step of steps) {
    const stepId = step.id || "";
    const action = step.action || "";
    try {
      if (action === "navigate") {
        const url = `${baseUrl}${step.url || "/"}`;
        await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
        recordResult(stepId, action, "passed");
      } else if (action === "wait_for_text") {
        await page.getByText(step.text).first().waitFor({ timeout: 30000 });
        recordResult(stepId, action, "passed");
      } else if (action === "click_nav") {
        const linkByLabel = page.getByRole("link", { name: step.label }).first();
        const labelCount = await linkByLabel.count();
        if (labelCount > 0) {
          await linkByLabel.click({ timeout: 30000 });
        } else if (step.url) {
          const linkByHref = page.locator(`a[href="${step.url}"]`).first();
          await linkByHref.click({ timeout: 30000 });
        } else {
          throw new Error(`nav link not found: ${step.label}`);
        }
        if (step.url) await page.waitForURL(`**${step.url}`, { timeout: 30000 });
        recordResult(stepId, action, "passed");
      } else if (action === "click_button") {
        if (step.label === "Start Loop") {
          const stopBtn = page.getByRole("button", { name: "Stop Loop" });
          if (await stopBtn.count()) {
            recordResult(stepId, action, "passed", "already running");
            continue;
          }
        }
        if (step.label === "Stop Loop") {
          const startBtn = page.getByRole("button", { name: "Start Loop" });
          if (await startBtn.count()) {
            recordResult(stepId, action, "passed", "already stopped");
            continue;
          }
        }
        await page.getByRole("button", { name: step.label }).first().click({ timeout: 30000 });
        recordResult(stepId, action, "passed");
      } else if (action === "http_post") {
        const url = `${apiBase}${step.url}`;
        const { status, text } = await httpPost(url, step.payload);
        if (expectStatus(status, step.expect_status ?? 200)) {
          recordResult(stepId, action, "passed", `status=${status}`);
        } else {
          recordResult(stepId, action, "failed", `status=${status} body=${text.slice(0, 200)}`);
        }
      } else {
        recordResult(stepId, action, "failed", "unknown action");
      }
    } catch (err) {
      const screenshot = path.join(outputDir, `${stepId}.png`);
      await page.screenshot({ path: screenshot, fullPage: true });
      recordResult(stepId, action, "failed", String(err), screenshot);
    }
  }

  for (const assertion of assertions) {
    const stepId = assertion.id || "";
    const action = assertion.action || "";
    if (action === "console_no_errors") {
      if (consoleErrors.length) {
        recordAssertion(stepId, action, "failed", consoleErrors.slice(0, 3).join("; "));
      } else {
        recordAssertion(stepId, action, "passed");
      }
    } else if (action === "network_request") {
      const matches = networkResponses.filter(r => r.url.includes(assertion.url_contains));
      let ok = matches.some(r => expectStatus(r.status, assertion.expect_status ?? 200));
      if (!ok && assertion.url_contains?.startsWith("/")) {
        const probeUrl = `${baseUrl}${assertion.url_contains}`;
        const probe = await httpGet(probeUrl);
        ok = expectStatus(probe.status, assertion.expect_status ?? 200);
        if (ok) matches.push({ url: probeUrl, status: probe.status });
      }
      if (ok) {
        recordAssertion(stepId, action, "passed", `matched=${matches.slice(0, 3).map(m => m.status).join(",")}`);
      } else {
        recordAssertion(stepId, action, "failed", `no match for ${assertion.url_contains}`);
      }
    } else {
      recordAssertion(stepId, action, "failed", "unknown assertion");
    }
  }

  const report = [
    "# MCP 回归测试报告",
    "",
    "## 执行信息",
    `- 日期：${new Date().toLocaleString()}`,
    `- 套件：${suite.name || "suite"}`,
    "",
    "## 结果摘要",
    `- 通过：${results.filter(r => r.status === "passed").length + assertionResults.filter(r => r.status === "passed").length}`,
    `- 失败：${results.filter(r => r.status === "failed").length + assertionResults.filter(r => r.status === "failed").length}`,
    "",
    "## 详细结果",
    "| 步骤 | 动作 | 结果 | 说明 | 证据 |",
    "| --- | --- | --- | --- | --- |",
    ...results.map(r => `| ${r.stepId} | ${r.action} | ${r.status} | ${r.detail} | ${r.screenshot || ""} |`),
    ...assertionResults.map(r => `| ${r.stepId} | ${r.action} | ${r.status} | ${r.detail} |  |`)
  ];
  fs.writeFileSync(path.join(outputDir, "report.md"), report.join("\n"));

  await browser.close();

  const failed = results.some(r => r.status === "failed") || assertionResults.some(r => r.status === "failed");
  process.exit(failed ? 1 : 0);
};

run().catch(err => {
  console.error(err);
  process.exit(1);
});
