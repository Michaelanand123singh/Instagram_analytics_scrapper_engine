/**
 * Example React component for the Instagram analytics panel.
 *
 * Plain fetch() calls against your CRM's own FastAPI backend (which proxies
 * to Instagram via instagram_router.py) — restyle to match your CRM's design
 * system. Assumes your API is reachable at the same origin under /instagram;
 * change API_BASE if your backend is mounted elsewhere.
 */
import { useEffect, useState } from "react";

const API_BASE = "/instagram";

export default function InstagramPanel() {
  const [status, setStatus] = useState(null);
  const [sessionId, setSessionId] = useState("");
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadStatus = async () => {
    const res = await fetch(`${API_BASE}/status`);
    setStatus(await res.json());
  };

  const loadLatest = async () => {
    const res = await fetch(`${API_BASE}/analytics/latest`);
    if (res.ok) setSnapshot(await res.json());
  };

  useEffect(() => {
    loadStatus();
    loadLatest();
  }, []);

  const handleConfigure = async () => {
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/configure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionid: sessionId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to configure");
      setSessionId("");
      await loadStatus();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFetchAnalytics = async () => {
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/analytics/fetch?amount=30`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to fetch analytics");
      setSnapshot(data);
      await loadStatus();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Instagram Analytics</h2>

      {!status?.configured && (
        <div>
          <p>Not connected yet. Paste an Instagram session cookie to connect.</p>
          <input
            type="text"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="sessionid cookie value"
          />
          <button onClick={handleConfigure} disabled={loading || !sessionId}>
            Connect
          </button>
        </div>
      )}

      {status?.configured && (
        <div>
          <p>Connected. Last fetched: {status.last_fetched_at || "never"}</p>
          <button onClick={handleFetchAnalytics} disabled={loading}>
            {loading ? "Fetching…" : "Fetch latest analytics"}
          </button>
        </div>
      )}

      {error && <p style={{ color: "red" }}>{error}</p>}

      {snapshot && (
        <div>
          <h3>@{snapshot.profile.username}</h3>
          <p>
            {snapshot.profile.follower_count} followers ·{" "}
            {snapshot.profile.following_count} following ·{" "}
            {snapshot.profile.media_count_total} posts
          </p>
          <ul>
            <li>Fetched posts: {snapshot.summary.fetched_count}</li>
            <li>Total likes: {snapshot.summary.total_likes}</li>
            <li>Total comments: {snapshot.summary.total_comments}</li>
            <li>Total views: {snapshot.summary.total_views}</li>
            <li>Avg engagement: {snapshot.summary.avg_engagement_pct}%</li>
          </ul>
        </div>
      )}
    </div>
  );
}
