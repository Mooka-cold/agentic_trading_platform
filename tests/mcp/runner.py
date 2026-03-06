import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

@dataclass
class StepResult:
    step_id: str
    action: str
    status: str
    detail: str = ""
    screenshot: Optional[str] = None

def _http_post(url: str, payload: Optional[dict] = None) -> Tuple[int, str]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url, data=data, headers=headers, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except URLError as e:
        return 0, str(e)

def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")

def _expect_status(actual: int, expected: Any) -> bool:
    if isinstance(expected, list):
        return actual in expected
    return actual == expected

def _write_report(path: str, suite_name: str, results: List[StepResult], assertions: List[StepResult]) -> None:
    total = len(results) + len(assertions)
    passed = sum(1 for r in results + assertions if r.status == "passed")
    failed = total - passed
    lines = [
        "# MCP 回归测试报告",
        "",
        "## 执行信息",
        f"- 日期：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 套件：{suite_name}",
        "",
        "## 结果摘要",
        f"- 通过：{passed}",
        f"- 失败：{failed}",
        "",
        "## 详细结果",
        "| 步骤 | 动作 | 结果 | 说明 | 证据 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results + assertions:
        evidence = r.screenshot or ""
        lines.append(f"| {r.step_id} | {r.action} | {r.status} | {r.detail} | {evidence} |")
    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def run_suite(suite_path: str, headless: bool = True) -> int:
    with open(suite_path, "r", encoding="utf-8") as f:
        suite = json.load(f)
    base_url = suite.get("base_url")
    api_base = suite.get("api_base")
    steps = suite.get("steps", [])
    assertions = suite.get("assertions", [])

    output_dir = os.path.join(os.path.dirname(suite_path), "output", _timestamp())
    _ensure_dir(output_dir)
    results: List[StepResult] = []
    assertion_results: List[StepResult] = []
    console_errors: List[str] = []
    network_responses: List[Tuple[str, int]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("dialog", lambda dialog: dialog.accept())
        page.on("response", lambda resp: network_responses.append((resp.url, resp.status)))

        for step in steps:
            step_id = step.get("id", "")
            action = step.get("action", "")
            try:
                if action == "navigate":
                    url = base_url + step.get("url", "/")
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    results.append(StepResult(step_id, action, "passed"))
                elif action == "wait_for_text":
                    page.get_by_text(step.get("text", "")).first.wait_for(timeout=30000)
                    results.append(StepResult(step_id, action, "passed"))
                elif action == "click_nav":
                    label = step.get("label", "")
                    page.get_by_role("link", name=label).first.click(timeout=30000)
                    if step.get("url"):
                        page.wait_for_url(f"**{step.get('url')}", timeout=30000)
                    results.append(StepResult(step_id, action, "passed"))
                elif action == "click_button":
                    label = step.get("label", "")
                    if label == "Start Loop":
                        if page.get_by_role("button", name="Stop Loop").count() > 0:
                            results.append(StepResult(step_id, action, "passed", "already running"))
                            continue
                    if label == "Stop Loop":
                        if page.get_by_role("button", name="Start Loop").count() > 0:
                            results.append(StepResult(step_id, action, "passed", "already stopped"))
                            continue
                    page.get_by_role("button", name=label).first.click(timeout=30000)
                    results.append(StepResult(step_id, action, "passed"))
                elif action == "http_post":
                    url = api_base + step.get("url", "")
                    status, body = _http_post(url, step.get("payload"))
                    expect_status = step.get("expect_status", 200)
                    if _expect_status(status, expect_status):
                        results.append(StepResult(step_id, action, "passed", f"status={status}"))
                    else:
                        results.append(StepResult(step_id, action, "failed", f"status={status} body={body[:200]}"))
                else:
                    results.append(StepResult(step_id, action, "failed", "unknown action"))
            except PlaywrightTimeoutError as e:
                screenshot = os.path.join(output_dir, f"{step_id}.png")
                page.screenshot(path=screenshot, full_page=True)
                results.append(StepResult(step_id, action, "failed", f"timeout: {e}", screenshot))
            except Exception as e:
                screenshot = os.path.join(output_dir, f"{step_id}.png")
                page.screenshot(path=screenshot, full_page=True)
                results.append(StepResult(step_id, action, "failed", str(e), screenshot))

        for assertion in assertions:
            step_id = assertion.get("id", "")
            action = assertion.get("action", "")
            if action == "console_no_errors":
                if console_errors:
                    assertion_results.append(StepResult(step_id, action, "failed", "; ".join(console_errors[:3])))
                else:
                    assertion_results.append(StepResult(step_id, action, "passed"))
            elif action == "network_request":
                url_contains = assertion.get("url_contains", "")
                expect_status = assertion.get("expect_status", 200)
                matched = [s for u, s in network_responses if url_contains in u]
                if matched and any(_expect_status(s, expect_status) for s in matched):
                    assertion_results.append(StepResult(step_id, action, "passed", f"matched={matched[:3]}"))
                else:
                    assertion_results.append(StepResult(step_id, action, "failed", f"no match for {url_contains}"))
            else:
                assertion_results.append(StepResult(step_id, action, "failed", "unknown assertion"))

        browser.close()

    report_path = os.path.join(output_dir, "report.md")
    _write_report(report_path, suite.get("name", "suite"), results, assertion_results)

    failures = [r for r in results + assertion_results if r.status == "failed"]
    return 1 if failures else 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True, help="Path to regression suite json")
    parser.add_argument("--headless", action="store_true", default=False)
    args = parser.parse_args()
    exit_code = run_suite(args.suite, headless=args.headless)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
