.PHONY: test evaluate handoff

test:
	python -m pytest -q

evaluate:
	python -m becher evaluate --run output/pipeline

handoff:
	python -m becher handoff --run output/pipeline --candidate 0000 --out output/handoff
