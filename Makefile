.PHONY: build dev shell setup start logs stop clean up

# ── Build ──────────────────────────────────────────────────────────────────────
build:
	docker compose build

# ── Run (attached, with logs streaming) ────────────────────────────────────────
dev:
	docker compose up

# ── Open shell ─────────────────────────────────────────────────────────────────
shell:
	docker compose run --rm api-gateway bash

# ── Project setup (copy .env, install deps, etc.) ──────────────────────────────
setup:
	@test -f .env || (echo "Creating .env from sample.env..." && cp sample.env .env)
	docker compose run --rm --no-deps api-gateway python scripts/setup.py install

# ── Start (detached) ───────────────────────────────────────────────────────────
start:
	docker compose up -d

# ── Tail logs ──────────────────────────────────────────────────────────────────
logs:
	docker compose logs -f

# ── Stop ───────────────────────────────────────────────────────────────────────
stop:
	docker compose down

# ── Full rebuild and run ───────────────────────────────────────────────────────
up: build dev

# ── Clean everything (volumes, unused images) ──────────────────────────────────
clean:
	docker compose down -v
	docker system prune -f
