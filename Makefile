.PHONY: bootstrap backend-run worker-run test-worker ui-dev

bootstrap:
	python3 scripts/bootstrap_structure.py

backend-run:
	uvicorn backend.app.main:app --reload

worker-run:
	python -m worker.app.main

test-worker:
	python -m pytest worker/tests

ui-dev:
	cd ui && npm run dev
