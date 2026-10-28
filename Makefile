.PHONY: test web api deploy-space

test:
	cd backend && uv run pytest -q

web:
	cd web && npm run dev

api:
	cd backend && uv run uvicorn finn.api:app --reload --port 8000

deploy-space:
	./scripts/deploy_space.sh
