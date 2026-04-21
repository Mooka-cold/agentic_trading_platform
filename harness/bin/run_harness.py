#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Tuple


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCENARIO_DIR = ROOT / "harness" / "scenarios"
REPORT_DIR = ROOT / "harness" / "reports"


SAFE_EVAL_GLOBALS = {
    "__builtins__": {},
    "len": len,
    "sum": sum,
    "min": min,
    "max": max,
    "all": all,
    "any": any,
    "isinstance": isinstance,
    "int": int,
    "float": float,
    "str": str,
    "dict": dict,
    "list": list,
    "tuple": tuple,
    "bool": bool,
}


def _load_json(path: pathlib.Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_url(base_url: str, path: str, params: Dict[str, Any] | None) -> str:
    base = base_url.rstrip("/")
    p = path if path.startswith("/") else f"/{path}"
    url = f"{base}{p}"
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{query}"
    return url


def _http_request(
    method: str,
    url: str,
    headers: Dict[str, str] | None,
    payload: Dict[str, Any] | None,
    timeout: int,
) -> Tuple[int, str, Any]:
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url=url, data=data, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            status = int(resp.status)
    except urllib.error.HTTPError as e:
        status = int(e.code)
        raw = e.read().decode("utf-8")
    except Exception as e:
        return 0, str(e), None

    parsed: Any = None
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    return status, raw, parsed


def _eval_assertion(expr: str, status: int, body: Any, text: str) -> Tuple[bool, str]:
    local_ctx = {"status": status, "body": body, "text": text}
    try:
        # Put runtime context into globals so comprehensions can access it.
        eval_globals = dict(SAFE_EVAL_GLOBALS)
        eval_globals.update(local_ctx)
        ok = bool(eval(expr, eval_globals, {}))
        if ok:
            return True, ""
        return False, f"assertion returned False: {expr}"
    except Exception as e:
        return False, f"assertion error: {expr}; error={e}"


def _run_step(step: Dict[str, Any], base_urls: Dict[str, str], default_timeout: int) -> Dict[str, Any]:
    req = step["request"]
    service = req["service"]
    if service not in base_urls:
        return {
            "name": step.get("name", "unnamed-step"),
            "passed": False,
            "error": f"unknown service: {service}",
        }

    timeout = int(req.get("timeout", default_timeout))
    url = _build_url(base_urls[service], req["path"], req.get("params"))
    status, text, body = _http_request(
        method=req.get("method", "GET"),
        url=url,
        headers=req.get("headers"),
        payload=req.get("json"),
        timeout=timeout,
    )

    assertion_results: List[Dict[str, Any]] = []
    all_ok = True
    for assertion in step.get("assertions", []):
        ok, err = _eval_assertion(assertion["expr"], status, body, text)
        assertion_results.append(
            {"name": assertion.get("name", assertion["expr"]), "passed": ok, "error": err}
        )
        if not ok:
            all_ok = False

    return {
        "name": step.get("name", "unnamed-step"),
        "url": url,
        "status": status,
        "passed": all_ok,
        "assertions": assertion_results,
        "response_preview": text[:500],
    }


def _run_scenario(
    scenario: Dict[str, Any], base_urls: Dict[str, str], default_timeout: int
) -> Dict[str, Any]:
    step_results = [_run_step(step, base_urls, default_timeout) for step in scenario.get("steps", [])]
    passed = all(s["passed"] for s in step_results) if step_results else False
    return {
        "id": scenario["id"],
        "title": scenario.get("title", ""),
        "priority": scenario.get("priority", "medium"),
        "passed": passed,
        "steps": step_results,
    }


def _write_reports(report: Dict[str, Any]) -> Tuple[pathlib.Path, pathlib.Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"harness_report_{ts}.json"
    md_path = REPORT_DIR / f"harness_report_{ts}.md"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    lines = [
        "# Harness Report",
        "",
        f"- Profile: `{report['profile']}`",
        f"- Passed: `{report['summary']['passed']}`",
        f"- Failed: `{report['summary']['failed']}`",
        "",
        "## Scenario Results",
    ]
    for scenario in report["scenarios"]:
        icon = "PASS" if scenario["passed"] else "FAIL"
        lines.append(f"- [{icon}] {scenario['id']} - {scenario['title']}")
    lines.append("")
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Trading harness runner")
    parser.add_argument("--profile", default="smoke", choices=["smoke", "regression", "replay"])
    parser.add_argument("--backend-url", default=os.getenv("HARNESS_BACKEND_URL", "http://localhost:3201"))
    parser.add_argument("--ai-engine-url", default=os.getenv("HARNESS_AI_ENGINE_URL", "http://localhost:3202"))
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()

    profile_index = _load_json(SCENARIO_DIR / "profiles.json")
    scenario_files = profile_index.get(args.profile, [])
    if not scenario_files:
        print(f"[ERROR] profile '{args.profile}' has no scenario files", file=sys.stderr)
        return 2

    base_urls = {"backend": args.backend_url, "ai_engine": args.ai_engine_url}
    scenario_results: List[Dict[str, Any]] = []
    for rel in scenario_files:
        scenario = _load_json(SCENARIO_DIR / rel)
        result = _run_scenario(scenario, base_urls, args.timeout)
        scenario_results.append(result)
        status_text = "PASS" if result["passed"] else "FAIL"
        print(f"[{status_text}] {result['id']} - {result['title']}")

    passed_count = sum(1 for s in scenario_results if s["passed"])
    failed_count = len(scenario_results) - passed_count
    report = {
        "profile": args.profile,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "summary": {"passed": passed_count, "failed": failed_count, "total": len(scenario_results)},
        "scenarios": scenario_results,
    }

    json_path, md_path = _write_reports(report)
    print(f"\nReport JSON: {json_path}")
    print(f"Report MD:   {md_path}")
    print(f"Summary: passed={passed_count}, failed={failed_count}, total={len(scenario_results)}")
    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
