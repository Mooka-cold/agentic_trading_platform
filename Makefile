.PHONY: harness-smoke harness-regression harness-replay

harness-smoke:
	python3 harness/bin/run_harness.py --profile smoke

harness-regression:
	python3 harness/bin/run_harness.py --profile regression

harness-replay:
	python3 harness/bin/run_harness.py --profile replay
