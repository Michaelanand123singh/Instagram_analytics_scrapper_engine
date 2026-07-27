from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired,
    LoginRequired,
    TwoFactorRequired,
)

BASE_DIR = Path(__file__).parent
SESSION_FILE = BASE_DIR / "session.json"

app = FastAPI(title="Instagrapi Test API", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
def root():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/analytics.html")
def analytics_page():
    return FileResponse(BASE_DIR / "static" / "analytics.html")

client = Client()
client.delay_range = [1, 3]  # human-like pause between Instagram requests, read-only usage only
_logged_in = False

if SESSION_FILE.exists():
    client.load_settings(SESSION_FILE)
    _logged_in = "authorization_data" in client.settings and bool(client.settings["authorization_data"])
else:
    # Persist device identity immediately so it stays stable across
    # server restarts, even before a login succeeds. Instagram treats
    # a changing device fingerprint as a new/untrusted device each time.
    client.dump_settings(SESSION_FILE)


class LoginRequest(BaseModel):
    username: str
    password: str
    verification_code: str | None = None


class SessionIdRequest(BaseModel):
    sessionid: str


class LoginResponse(BaseModel):
    status: str
    detail: str


def require_login():
    if not _logged_in:
        raise HTTPException(status_code=401, detail="Not logged in yet. Call POST /login first.")


@app.get("/health")
def health():
    return {"status": "ok", "logged_in": _logged_in}


@app.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    global _logged_in
    try:
        client.login(
            payload.username,
            payload.password,
            verification_code=payload.verification_code or "",
        )
        client.dump_settings(SESSION_FILE)
        _logged_in = True
        return LoginResponse(status="ok", detail="Logged in and session saved.")
    except TwoFactorRequired:
        raise HTTPException(
            status_code=428,
            detail="Two-factor code required. Retry POST /login with verification_code set.",
        )
    except ChallengeRequired as e:
        challenge = getattr(client, "last_json", {}) or {}
        raise HTTPException(
            status_code=428,
            detail={
                "message": (
                    "Instagram issued a challenge (email/SMS code or app approval). "
                    "Complete it in the Instagram app/website, then retry /login."
                ),
                "error": str(e),
                "raw": challenge,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Login failed: {e}")


@app.post("/login/sessionid", response_model=LoginResponse)
def login_sessionid(payload: SessionIdRequest):
    global _logged_in
    try:
        client.login_by_sessionid(payload.sessionid.strip())
        client.dump_settings(SESSION_FILE)
        _logged_in = True
        return LoginResponse(status="ok", detail="Logged in via sessionid and session saved.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Session login failed: {e}")


@app.post("/logout")
def logout():
    global _logged_in
    _logged_in = False
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
    return {"status": "ok", "detail": "Session cleared."}


@app.get("/account/info")
def account_info():
    require_login()
    try:
        me = client.account_info()
        return me.model_dump()
    except LoginRequired:
        raise HTTPException(status_code=401, detail="Session expired, log in again via /login.")


@app.get("/user/{username}")
def user_info(username: str):
    require_login()
    try:
        user_id = client.user_id_from_username(username)
        info = client.user_info(user_id)
        return info.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _media_type_label(media_type: int, product_type: str) -> str:
    product_type = (product_type or "").lower()
    if media_type == 1:
        return "photo"
    if media_type == 8:
        return "carousel"
    if media_type == 2:
        if product_type == "clips":
            return "reel"
        if product_type == "igtv":
            return "igtv"
        return "video"
    return "other"


@app.get("/analytics")
def analytics(amount: int = 30):
    require_login()
    try:
        acc = client.account_info()
        profile = client.user_info(acc.pk)
        medias = client.user_medias(acc.pk, amount=amount)
    except LoginRequired:
        raise HTTPException(status_code=401, detail="Session expired, log in again via /login.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch analytics: {e}")

    items = []
    type_counts: dict[str, int] = {}
    total_likes = total_comments = total_views = 0

    for m in medias:
        mtype = _media_type_label(m.media_type, m.product_type)
        type_counts[mtype] = type_counts.get(mtype, 0) + 1

        views = m.play_count or m.view_count or 0
        likes = m.like_count or 0
        comments = m.comment_count or 0
        total_likes += likes
        total_comments += comments
        total_views += views

        permalink_base = "reel" if mtype == "reel" else "p"
        items.append(
            {
                "pk": str(m.pk),
                "code": m.code,
                "type": mtype,
                "taken_at": m.taken_at.isoformat() if m.taken_at else None,
                "caption": (m.caption_text or "")[:120],
                "like_count": likes,
                "comment_count": comments,
                "view_count": views,
                "engagement": likes + comments,
                "permalink": f"https://www.instagram.com/{permalink_base}/{m.code}/",
                "thumbnail_url": str(m.thumbnail_url) if m.thumbnail_url else None,
            }
        )

    items.sort(key=lambda x: x["taken_at"] or "", reverse=True)
    fetched_count = len(items)
    follower_count = profile.follower_count or 0

    avg_likes = round(total_likes / fetched_count, 1) if fetched_count else 0
    avg_comments = round(total_comments / fetched_count, 1) if fetched_count else 0
    avg_engagement_pct = (
        round(((total_likes + total_comments) / fetched_count) / follower_count * 100, 3)
        if fetched_count and follower_count
        else 0
    )

    top_by_engagement = sorted(items, key=lambda x: x["engagement"], reverse=True)[:5]
    top_by_views = sorted([i for i in items if i["view_count"]], key=lambda x: x["view_count"], reverse=True)[:5]

    return {
        "profile": {
            "username": profile.username,
            "full_name": profile.full_name,
            "follower_count": follower_count,
            "following_count": profile.following_count,
            "media_count_total": profile.media_count,
        },
        "summary": {
            "fetched_count": fetched_count,
            "type_counts": type_counts,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_views": total_views,
            "avg_likes": avg_likes,
            "avg_comments": avg_comments,
            "avg_engagement_pct": avg_engagement_pct,
            "top_by_engagement": top_by_engagement,
            "top_by_views": top_by_views,
        },
        "media": items,
    }
