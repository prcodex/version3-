.PHONY: validate compile test eval-dry
validate:
	python -m m3xa_souls.validate
compile:
	python -m m3xa_souls.compiler --out dist
test:
	pytest -q
eval-dry:
	python eval/run_eval.py --dry-run
