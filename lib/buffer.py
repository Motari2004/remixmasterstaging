"""
Buffer POST logic. Config comes in as a dict (from Neon) instead of
settings.json.
"""
import json
import requests


BUFFER_API_URL = "https://api.buffer.com"


class LimitReached(Exception):
    """Buffer's scheduled-post limit hit for this channel."""


def _utf16_len(s):
    return len(s.encode("utf-16-le")) // 2


def _build_payload(channel_id, video_url, title, caption, platform):
    platform = (platform or "youtube").lower()

    if platform == "instagram":
        text = f"{title}\n\n{caption}" if caption else title
        if len(text) > 2200:
            text = text[:2197].rstrip() + "..."
        metadata = {"instagram": {
            "type": "reel", "shouldShareToFeed": True, "isAiGenerated": True,
        }}

    elif platform == "tiktok":
        text = f"{title}\n\n{caption}" if caption else title
        if len(text) > 2200:
            text = text[:2197].rstrip() + "..."
        metadata = {"tiktok": {
            "title": (title or "")[:150],
            "isAiGenerated": True,
        }}

    elif platform == "facebook":
        text = f"{title}\n\n{caption}" if caption else title
        if len(text) > 5000:
            text = text[:4997].rstrip() + "..."
        metadata = {"facebook": {"type": "reel"}}

    else:  # youtube
        t = title or ""
        if _utf16_len(t) > 100:
            while t and _utf16_len(t) > 100:
                t = t[:-1].rstrip()
            t = t[:-3].rstrip() + "..."
        text = caption or ""
        metadata = {"youtube": {
            "title": t, "categoryId": "24",
            "privacy": "public", "madeForKids": True,
        }}

    return text, metadata


def publish(niche, video_url, title, caption, cfg):
    api_key = (cfg.get("buffer_api_key") or "").strip()
    if not api_key:
        raise RuntimeError(f"No buffer_api_key for niche '{niche}'")
    channel_id = (cfg.get("buffer_channel_id") or "").strip()
    if not channel_id:
        raise RuntimeError(f"No buffer_channel_id for niche '{niche}'")
    platform = (cfg.get("platform") or "youtube").lower()

    text, metadata = _build_payload(channel_id, video_url, title, caption, platform)

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id dueAt status } }
        ... on MutationError { message }
      }
    }
    """
    payload = {"query": mutation, "variables": {"input": {
        "channelId": channel_id,
        "text": text,
        "schedulingType": "automatic",
        "mode": "addToQueue",
        "assets": [{"video": {"url": video_url}}],
        "metadata": metadata,
    }}}

    r = requests.post(
        BUFFER_API_URL, json=payload,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        timeout=30,
    )
    result = r.json()
    blob = json.dumps(result).lower()

    if ("scheduled posts limit reached" in blob
            or ("scheduled posts limit" in blob and "reached" in blob)):
        raise LimitReached("Scheduled posts limit reached")

    if "errors" in result:
        raise RuntimeError(str(result["errors"]))

    br = (result.get("data") or {}).get("createPost") or {}
    if isinstance(br, dict) and br.get("message"):
        msg = br["message"]
        if "scheduled posts limit" in msg.lower():
            raise LimitReached(msg)
        raise RuntimeError(msg)

    return result