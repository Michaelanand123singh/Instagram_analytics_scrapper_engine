# CRM Integration — Instagram Analytics

Drop-in pieces to add Instagram analytics (session config from the frontend,
fetch-and-store, read stored analytics) into your existing React + FastAPI +
MongoDB CRM. Built for a **single Instagram account for the whole CRM** (not
per-user).

## Files

| File | Copy to | Purpose |
|---|---|---|
| `instagram_service.py` | your CRM backend | Core logic: login via sessionid, fetch analytics, persist to MongoDB |
| `instagram_router.py` | your CRM backend | FastAPI endpoints your React app calls |
| `InstagramPanel.example.jsx` | your CRM frontend | Example UI — restyle to match your design system |

## Backend setup

1. Copy `instagram_service.py` and `instagram_router.py` into your FastAPI
   backend (same folder as your other routers/services is fine).

2. Install dependencies in your CRM backend's environment:
   ```bash
   pip install instagrapi motor
   ```

3. In your main FastAPI app, wire the router to your real Mongo database:

   ```python
   from motor.motor_asyncio import AsyncIOMotorClient
   from instagram_router import router as instagram_router, get_instagram_service
   from instagram_service import InstagramService

   mongo_client = AsyncIOMotorClient(YOUR_MONGO_URI)
   db = mongo_client[YOUR_DB_NAME]

   app.dependency_overrides[get_instagram_service] = lambda: InstagramService(db)
   app.include_router(instagram_router)
   ```

That's it — no local `session.json` file needed. The Instagram session and
device fingerprint are stored in the `instagram_session` collection instead,
so it survives restarts and works even if your backend runs multiple
processes/instances.

## Endpoints this adds

| Method | Path | Purpose |
|---|---|---|
| GET | `/instagram/status` | Whether Instagram is configured, last fetch time |
| POST | `/instagram/configure` | Body: `{"sessionid": "..."}` — connect the account |
| POST | `/instagram/deconfigure` | Clear the stored session |
| POST | `/instagram/analytics/fetch?amount=30` | Pull fresh data from Instagram, save a snapshot, return it |
| GET | `/instagram/analytics/latest` | Return the most recently saved snapshot (fast, no Instagram call) |
| GET | `/instagram/analytics/history?limit=20` | List past snapshots (summary only, for trend charts) |

## How your team gets the `sessionid`

Same as documented in the main project README:
1. Log into instagram.com normally in a browser.
2. DevTools → Application/Storage → Cookies → `https://www.instagram.com`.
3. Copy the `sessionid` cookie value.
4. Paste it into the CRM's Instagram panel (calls `POST /instagram/configure`).

This reuses an already-trusted session, avoiding the automated-login
security checkpoints that plain password login triggers.

## Frontend

`InstagramPanel.example.jsx` is a minimal, unstyled reference — copy it into
your components folder, restyle it with your existing CRM UI components, and
mount it wherever your Instagram/social section lives.

## Data model (MongoDB)

- **`instagram_session`** — one document (`_id: "singleton"`) holding the
  serialized instagrapi client settings (device fingerprint, cookies,
  auth token) and a `logged_in` flag. Sensitive — treat like a credentials
  table (restrict DB access accordingly).
- **`instagram_analytics_snapshots`** — one document per fetch, with
  `fetched_at`, `profile`, `summary`, and the full `media` list for that
  pull. This will grow over time; if snapshot volume becomes a concern,
  consider a TTL index on `fetched_at` or dropping `media` from all but the
  most recent N snapshots (history/list endpoints already exclude `media`
  by default).

## Safety notes (same as the main project)

- Keep fetch frequency low (weekly/manual, not hourly) — see the main
  project README's "Notes on account safety" section for why.
- This is read-only: no posting/following/DM endpoints are included here.
- The service throttles Instagram requests (`client.delay_range = [1, 3]`)
  automatically.
