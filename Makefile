.PHONY: test web api deploy-space ingest eval

test:
	cd backend && uv run pytest -q

web:
	cd web && npm run dev

api:
	cd backend && uv run uvicorn finn.api:app --reload --port 8000

deploy-space:
	./scripts/deploy_space.sh

# Local fallback for the scheduled GitHub Actions ingest (.github/workflows/ingest.yml).
ingest:
	git pull --rebase origin main
	cd backend && uv run python -m finn.ingest --days 7
	git add data/snapshot && (git diff --cached --quiet || git commit -m "chore: ingest (local)")
	git push origin main
	./scripts/deploy_space.sh

eval:
	cd backend && uv run python -m eval.run
