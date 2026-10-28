.PHONY: test

test:
	cd backend && uv run pytest -q
