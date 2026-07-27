"""
Instagram analytics service for the CRM backend.

Wraps instagrapi (private Instagram API client) behind a service class that:
  - stores the logged-in session/device fingerprint in MongoDB instead of a
    local file, so it survives restarts and works across processes/instances
  - fetches profile + per-post analytics and saves timestamped snapshots

Requires: `pip install instagrapi motor`

Assumes an async Motor database object (`motor.motor_asyncio.AsyncIOMotorDatabase`).
If your CRM uses sync PyMongo instead, drop the `await`/`async` keywords and
remove the `asyncio.to_thread(...)` wrappers (call the instagrapi methods
directly, since PyMongo calls are already sync).
"""

import asyncio
from datetime import datetime, timezone

from instagrapi import Client

SESSION_COLLECTION = "instagram_session"
SESSION_DOC_ID = "singleton"  # single Instagram account for the whole CRM
SNAPSHOT_COLLECTION = "instagram_analytics_snapshots"


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


class InstagramService:
    def __init__(self, db):
        self.db = db

    async def _load_client(self) -> Client:
        """Build a Client, restoring saved device/session state from Mongo if present."""
        client = Client()
        client.delay_range = [1, 3]  # throttle to avoid bursty/bot-like traffic

        doc = await self.db[SESSION_COLLECTION].find_one({"_id": SESSION_DOC_ID})
        if doc and doc.get("settings"):
            client.set_settings(doc["settings"])
        else:
            # Persist a stable device fingerprint immediately, even before
            # login succeeds — a changing fingerprint is a major red flag
            # to Instagram's automation detection.
            await self._save_settings(client)
        return client

    async def _save_settings(self, client: Client, logged_in: bool | None = None):
        update = {"settings": client.get_settings(), "updated_at": datetime.now(timezone.utc)}
        if logged_in is not None:
            update["logged_in"] = logged_in
        await self.db[SESSION_COLLECTION].update_one(
            {"_id": SESSION_DOC_ID}, {"$set": update}, upsert=True
        )

    async def is_configured(self) -> bool:
        doc = await self.db[SESSION_COLLECTION].find_one({"_id": SESSION_DOC_ID})
        return bool(doc and doc.get("logged_in"))

    async def configure_with_sessionid(self, sessionid: str) -> dict:
        """Log in by importing an already-authenticated Instagram sessionid cookie.

        This is the recommended path — see the main project README for how
        an operator obtains a sessionid (log into instagram.com, copy the
        `sessionid` cookie from devtools). Avoids Instagram's automated-login
        security checkpoints, which password-based login frequently triggers.
        """
        client = await self._load_client()
        try:
            await asyncio.to_thread(client.login_by_sessionid, sessionid.strip())
        except Exception as e:
            raise ValueError(f"Session login failed: {e}") from e
        await self._save_settings(client, logged_in=True)
        return {"status": "ok", "detail": "Instagram session configured."}

    async def clear_configuration(self):
        await self.db[SESSION_COLLECTION].delete_one({"_id": SESSION_DOC_ID})

    async def fetch_and_save_analytics(self, amount: int = 30) -> dict:
        client = await self._load_client()
        doc = await self.db[SESSION_COLLECTION].find_one({"_id": SESSION_DOC_ID})
        if not doc or not doc.get("logged_in"):
            raise PermissionError("Instagram is not configured yet. Call configure_with_sessionid first.")

        def _pull():
            acc = client.account_info()
            profile = client.user_info(acc.pk)
            medias = client.user_medias(acc.pk, amount=amount)
            return profile, medias

        try:
            profile, medias = await asyncio.to_thread(_pull)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch analytics from Instagram: {e}") from e

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
        avg_engagement_pct = (
            round(((total_likes + total_comments) / fetched_count) / follower_count * 100, 3)
            if fetched_count and follower_count
            else 0
        )

        snapshot = {
            "fetched_at": datetime.now(timezone.utc),
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
                "avg_likes": round(total_likes / fetched_count, 1) if fetched_count else 0,
                "avg_comments": round(total_comments / fetched_count, 1) if fetched_count else 0,
                "avg_engagement_pct": avg_engagement_pct,
            },
            "media": items,
        }

        result = await self.db[SNAPSHOT_COLLECTION].insert_one(snapshot)
        snapshot["_id"] = str(result.inserted_id)
        return snapshot

    async def get_latest_snapshot(self) -> dict | None:
        doc = await self.db[SNAPSHOT_COLLECTION].find_one(sort=[("fetched_at", -1)])
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_snapshot_history(self, limit: int = 20) -> list[dict]:
        cursor = self.db[SNAPSHOT_COLLECTION].find(
            {}, {"media": 0}  # exclude the heavy per-post list for list views
        ).sort("fetched_at", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs
