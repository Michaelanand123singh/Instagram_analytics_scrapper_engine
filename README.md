# Instagram Analytics Scraper Engine

A local FastAPI service and web dashboard for pulling Instagram profile and
post/reel analytics, built on top of the [instagrapi](https://github.com/subzeroid/instagrapi)
private-API library (vendored in this repo — original library docs kept in
[`INSTAGRAPI_LIBRARY_README.md`](INSTAGRAPI_LIBRARY_README.md)).

It gives you:
- A **Test Console** (`/`) to log in and try the API endpoints from a browser.
- An **Analytics Dashboard** (`/analytics.html`) showing follower stats, per-post
  likes/comments/views, content-type breakdown, and top-performing posts.
- A small JSON API other tools (e.g. a CRM) can call directly.

## ⚠️ Read this first

- `instagrapi` talks to Instagram's **private mobile API**, not the official
  Graph API. This is **against Instagram's Terms of Service** and carries a
  real risk of account checkpoints, temporary restrictions, or bans —
  especially for password-based login, which frequently triggers a security
  checkpoint that this library cannot resolve automatically.
- Everything in this repo is **read-only** (login + fetch data). There are no
  posting, liking, following, or messaging endpoints.
- Runs on `127.0.0.1` only — not exposed to the internet. Don't change that
  without adding real authentication first.
- **Never commit `session.json`.** It contains a live, working Instagram
  session — equivalent to your password. It's already git-ignored; keep it
  that way.
- Use a **test/secondary Instagram account** where possible. If you use a
  real/primary account, treat it as genuinely at-risk.

## Prerequisites

- Python **3.10+**
- Git

## Setup

```bash
git clone https://github.com/Michaelanand123singh/Instagram_analytics_scrapper_engine.git
cd Instagram_analytics_scrapper_engine

# create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# install instagrapi (this repo) in editable mode
pip install -e .

# install the API/dashboard dependencies
pip install -r requirements-api.txt
```

## Running the server

```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Then open **http://127.0.0.1:8000/** in your browser.

On first run, a `session.json` is created automatically to hold a stable
device fingerprint — this persists across restarts and is important for
account safety (see [Notes on account safety](#notes-on-account-safety)).

## Logging in

There are two ways to log in, from the **Test Console** at `/`:

### Option A — Username & password (may hit a checkpoint)

Enter your username, password, and (if prompted) a 2FA/verification code.
Instagram frequently responds to fresh automated logins with a **security
checkpoint** ("challenge required") that must be completed manually in the
real Instagram app or website — this library cannot solve it for you. If that
happens, use Option B instead.

### Option B — Import an already-logged-in session (recommended)

This reuses a session Instagram has already fully trusted via its own normal
web login, skipping the checkpoint flow entirely:

1. Log into [instagram.com](https://instagram.com) normally in your browser.
2. Open DevTools (`F12`) → **Application** (Chrome/Edge) or **Storage**
   (Firefox) tab → **Cookies** → `https://www.instagram.com`.
3. Copy the value of the **`sessionid`** cookie.
4. On the Test Console, paste it into the **"Import an already-logged-in
   session"** box and click **Import session**.

Once logged in (either way), the session is saved to `session.json` and
reused automatically on future server restarts — you won't need to log in
again unless you explicitly log out or the session expires.

## Using the dashboard

- **Test Console** (`/`) — login, logout, fetch your own account info, look
  up any public username.
- **Analytics Dashboard** (`/analytics.html`) — set how many recent posts to
  analyze, click **Fetch analytics**, and see:
  - Profile summary (followers/following/total posts)
  - Stat tiles (total likes/comments/views, averages, engagement rate)
  - Likes-per-post chart with hover details
  - Content type breakdown (photo/video/carousel/reel/igtv)
  - Top 5 posts by engagement and by views
  - Full sortable table of every fetched post/reel with a direct link

## API reference

All endpoints are JSON. Login is required (via `/login` or
`/login/sessionid`) before calling any data endpoint.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Server status and login state |
| POST | `/login` | Log in with `username`, `password`, optional `verification_code` |
| POST | `/login/sessionid` | Log in by importing a `sessionid` cookie value |
| POST | `/logout` | Clear the saved session |
| GET | `/account/info` | Your own account's profile info |
| GET | `/user/{username}` | Public profile info for any username |
| GET | `/analytics?amount=30` | Profile + per-post analytics for your `amount` most recent posts/reels |

## Notes on account safety

- The client reuses a **persistent device fingerprint** (stored in
  `session.json`) instead of generating a new one on every run — a changing
  fingerprint is one of the biggest triggers for Instagram's automation
  detection.
- Requests are throttled with a randomized 1–3 second delay
  (`client.delay_range` in `api.py`) to avoid bursty, bot-like traffic.
- Keep `amount` in `/analytics` moderate (tens, not hundreds) per run, and
  avoid running this on a tight automated schedule (e.g. hourly). A weekly or
  occasional manual pull is a much safer usage pattern.
- Stick to **one Instagram account per machine/session** where possible —
  repeatedly logging in and out of different accounts from the same device
  looks more suspicious to Instagram than steady use of one account.

## Project structure

```
api.py                          FastAPI app: login, session handling, analytics endpoints
static/index.html               Test Console (login + basic endpoint testing UI)
static/analytics.html           Analytics dashboard
instagrapi/                     instagrapi library source (vendored)
requirements-api.txt            Dependencies for api.py (FastAPI, uvicorn)
pyproject.toml                  instagrapi package definition
INSTAGRAPI_LIBRARY_README.md    Original upstream instagrapi documentation
```

## Credits & license

This repository vendors [instagrapi](https://github.com/subzeroid/instagrapi)
by Mark Subzeroid and contributors, licensed under the MIT License (see
[`LICENSE`](LICENSE)). `api.py` and everything under `static/` are additions
built on top of it for this project.
