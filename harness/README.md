# Harness Engineering (Trading Correctness First)

This harness validates trading correctness with repeatable API scenarios and machine-readable reports.

## Quick Start

Run smoke checks:

```bash
make harness-smoke
```

Run full regression:

```bash
make harness-regression
```

Run replay profile:

```bash
make harness-replay
```

## Structure

- `harness/bin/run_harness.py`: scenario runner.
- `harness/scenarios/`: scenario definitions.
- `harness/fixtures/`: fixture placeholders.
- `harness/reports/`: generated reports (ignored by git except `.gitkeep`).

## Profiles

- `smoke`: fast correctness gate for key trading paths.
- `regression`: broader set for pre-merge/nightly checks.
- `replay`: deterministic checks intended for historical playback extension.

## Report Outputs

Each run writes:

- `harness/reports/harness_report_<timestamp>.json`
- `harness/reports/harness_report_<timestamp>.md`

## Scenario Schema

Each scenario is a JSON file with:

- `id`, `title`, `priority`
- `steps[]` with:
  - `request`: `service`, `method`, `path`, optional `params`, optional `json`
  - `assertions[]`: `name`, `expr`

Assertion expression context:

- `status`: HTTP status code
- `body`: parsed JSON body (or `null`)
- `text`: raw response text

Example assertion:

```json
{
  "name": "balance exists",
  "expr": "status == 200 and isinstance(body, dict) and isinstance(body.get('balance'), (int, float))"
}
```
