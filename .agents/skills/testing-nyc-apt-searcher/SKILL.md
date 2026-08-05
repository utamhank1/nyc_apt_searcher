---
name: testing-nyc-apt-searcher
description: How to boot, seed and end-to-end test the NYC Apartment Searcher app (FastAPI backend + Next.js dashboard) locally, including auth, webhook signature, rescore and calendar flows.
---

# Testing NYC Apartment Searcher locally

## Boot

Backend (port 8000):
```bash
cd backend
cp ../.env.example .env          # then edit, see below
PYTHONPATH=. venv/bin/uvicorn app.main:app --port 8000
```
Frontend (port 3000):
```bash
cd frontend
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

`backend/.env` keys that matter for testing:
- `API_KEY=...` — the dashboard passkey. Enter the *same* value on the landing page; it is stored in `localStorage` as `apt_api_key`.
- `DATABASE_URL=sqlite+aiosqlite:///./apt_searcher.db` (default) → DB file at `backend/apt_searcher.db`.
- `RESEND_WEBHOOK_SECRET=whsec_<base64>` — required for `/api/v1/webhooks/email-reply`; without it that route returns 503 (everything else still works).

Resend / Telegram / Google Maps / Google Calendar / RapidAPI are normally unconfigured. Scrapes return 0 listings and alerts/emails no-op with warning logs — that is expected, not a failure.

## Gotchas

- **Backgrounded servers get killed.** Launching uvicorn with a plain `&` from a one-shot shell dies when the tool call ends. Use `(setsid env PYTHONPATH=. <venv>/bin/uvicorn app.main:app --port 8000 > /tmp/backend.log 2>&1 < /dev/null &)` and then poll `/health`. Always confirm the old process is dead (`ps aux | grep uvicorn`) before restarting — otherwise the new one silently fails with `address already in use` and you keep testing the stale config.
- **Chained commands after `pkill`/`sed` may not run** if the shell is torn down mid-call. After editing `.env`, re-`grep` it to confirm the edit landed before drawing conclusions from a restart.
- **Chrome may not be installed.** If `google-chrome` is only a stub that POSTs to `localhost:29229`, install it: `wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && sudo dpkg -i`. Launch with `--remote-debugging-port=29229 --user-data-dir=/tmp/chromeprofile`, then `wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz`.
- **Rotating `API_KEY` mid-session**: the frontend clears `apt_api_key` from localStorage automatically on any non-calendar 401, so just reload `/leads` once and you'll be returned to the landing page — no devtools needed.
- **Typing into inputs can drop characters** (notably shifted ones). Re-read the field after typing; prefer names without capitals/spaces, and `ctrl+a` before retyping.

## Seeding data (the DB starts empty)

```bash
# stub listing, no scraping required
curl -s -X POST localhost:8000/api/v1/leads/submit-url \
  -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"url":"https://streeteasy.com/building/east-village-lofts/12345"}'
# then enrich it so scoring has something to work with
sqlite3 backend/apt_searcher.db "update listings set borough='Manhattan', neighborhood='East Village',
  price=2500, beds=1, baths=1, amenities='[\"dishwasher\",\"elevator\"]' where id=1"
```
For calendar UI without Google OAuth, insert a fake connection so the "Disconnect" button renders:
```sql
insert into calendar_connections (user_email,refresh_token,is_main_user,connected_at)
values ('tester@example.com','fake-refresh-token',1,datetime('now'));
```

## Exercising specific features

- **Rescore** (`POST /api/v1/leads/rescore`) has **no UI trigger** — call it with curl and click "Refresh" on the Leads page to show the score change. To test that a hard-filtering search doesn't wipe a score, create two active searches: one matching (e.g. Manhattan/East Village) and one that filters the listing out (e.g. Queens), making sure the filtering one has the **higher id** so it's evaluated last.
- **Webhook signature**: Svix scheme — HMAC-SHA256 over `{svix-id}.{svix-timestamp}.{raw body}`, key = `base64decode(secret after "whsec_")`, header `svix-signature: v1,<base64 digest>`, 5-minute tolerance. Always include a *tampered-body-with-valid-signature* case; a signature check that only validates headers would otherwise pass.
- **Searches page**: Edit/Delete buttons are hidden while a search is Active, so the API's "cannot edit/delete an active search" refusal is not reachable from the UI.
- **Known bug to watch for**: the Delete button in `frontend/src/app/searches/page.tsx` calls `api.get('/api/v1/searches/{id}')` first, but no such GET route exists → 405 → the wrapper throws and the DELETE never fires. Delete may therefore appear to do nothing. Verify deletion against the DB / backend access log, not just the UI. The backend `DELETE /api/v1/searches/{id}` itself works.
- **Non-2xx-looking failures**: several endpoints return HTTP 200 with `{"error": "..."}` instead of a 4xx. Assert on the response body, not just the status code.
- **Dev-only console noise**: `Warning: Function components cannot be given refs ... DialogClose` (from `src/components/ui/dialog.tsx`) fires whenever a dialog opens and drives the Next.js "1 error" overlay badge. Pre-existing, not a regression.
- **Settings** saves to an in-memory config; values do not survive a backend restart. Known pre-existing issue.

## Railway deploy sanity check

`railway.json` / `Procfile` start command: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}`, healthcheck `/health`. To verify boot resilience, delete optional settings lines from `.env` (e.g. `RESEND_WEBHOOK_SECRET`) and confirm uvicorn starts, the scheduler logs `Scheduler started`, `/health` is 200, and only the dependent route degrades.

## Devin Secrets Needed

None. `API_KEY` and `RESEND_WEBHOOK_SECRET` are values you choose locally. Real end-to-end coverage of email sending, Telegram alerts, Google Calendar OAuth and scraping would require `RESEND_API_KEY`, `TELEGRAM_BOT_TOKEN`, `GOOGLE_CALENDAR_CLIENT_ID`/`GOOGLE_CALENDAR_CLIENT_SECRET`, `GOOGLE_MAPS_API_KEY` and `RAPIDAPI_KEY`.
