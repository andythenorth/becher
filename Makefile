.PHONY: test pipeline evaluate handoff

test:
	python -m pytest -q

pipeline:
	python -m becher pipeline --seed 1267 --designs 12 --workers 4 --facade-mode decals --edge-contrast on --roof-colours on --out output/pipeline

evaluate:
	python -m becher evaluate --run output/pipeline

handoff:
	python -m becher handoff --run output/pipeline --candidate 0000 --out output/handoff
