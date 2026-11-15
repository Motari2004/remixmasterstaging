"""
Add title + categoryId to the YouTube branch of _buffer_queue_post in
staging-service/app.py.

Buffer's YouTube API requires both. The pipeline's app.py already sends
them; the drain's buffer code doesn't.

Also wires made_for_kids through, if the niche config has it.
"""
import os, sys, shutil, datetime, ast

APP = r"C:\Users\PC\Desktop\staging-service\app.py"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

if not os.path.exists(APP):
    print(f"❌ Not found: {APP}"); sys.exit(1)

src = open(APP, encoding="utf-8").read()
backup = f"{APP}.bak.{ts}"
shutil.copy2(APP, backup)
print(f"📦 Backup: {backup}")
print()

if "youtube_payload_fixed" in src:
    print("Already patched.")
    sys.exit(0)


# ---------------------------------------------------------------
# 1. Extend _buffer_queue_post signature to accept cfg
# ---------------------------------------------------------------
old_sig = '''def _buffer_queue_post(api_key, channel_id, video_url, title, caption, platform="instagram"):'''
new_sig = '''def _buffer_queue_post(api_key, channel_id, video_url, title, caption, platform="instagram", cfg=None):'''
if old_sig not in src:
    print("❌ Could not find _buffer_queue_post signature")
    shutil.copy2(backup, APP); sys.exit(1)
src = src.replace(old_sig, new_sig, 1)
print("✅ Extended signature with cfg param")


# ---------------------------------------------------------------
# 2. Build proper YouTube metadata inside _buffer_queue_post
# ---------------------------------------------------------------
old_meta = '''    plat = (platform or "").lower()
    metadata = {}
    if plat == "instagram":
        metadata = {
            "instagram": {
                "type": "reel",
                "shouldShareToFeed": True,
                "isAiGenerated": True,
            }
        }
    elif plat == "facebook":
        metadata = {
            "facebook": {
                "type": "reel",
            }
        }
    # tiktok / youtube / others: no metadata block'''

new_meta = '''    plat = (platform or "").lower()
    metadata = {}
    if plat == "instagram":
        metadata = {
            "instagram": {
                "type": "reel",
                "shouldShareToFeed": True,
                "isAiGenerated": True,
            }
        }
    elif plat == "facebook":
        metadata = {
            "facebook": {
                "type": "reel",
            }
        }
    elif plat == "youtube":
        # youtube_payload_fixed
        # Buffer requires title + categoryId for every YouTube post.
        # Trim title to 100 chars (YouTube limit) before sending.
        t = (title or "").strip()
        if not t:
            t = (caption or "").strip().split("\\n")[0][:100] or "ObiEdits"
        if len(t) > 100:
            t = t[:97].rstrip() + "..."
        mfk = False
        if isinstance(cfg, dict):
            mfk = bool(cfg.get("made_for_kids", False))
        metadata = {
            "youtube": {
                "title": t,
                "categoryId": "24",
                "privacy": "public",
                "madeForKids": mfk,
            }
        }
    # tiktok / others: no metadata block'''

if old_meta not in src:
    print("❌ Could not find the metadata block")
    shutil.copy2(backup, APP); sys.exit(1)
src = src.replace(old_meta, new_meta, 1)
print("✅ YouTube branch now includes title + categoryId + madeForKids")


# ---------------------------------------------------------------
# 3. Pass cfg through from _drain_niche to _buffer_queue_post
# ---------------------------------------------------------------
old_call = '''            bid = _buffer_queue_post(
                api_key,
                channel_id,
                row["video_url"],
                row["title"],
                row["caption"],
                platform=cfg.get("platform", "instagram"),
            )'''
new_call = '''            bid = _buffer_queue_post(
                api_key,
                channel_id,
                row["video_url"],
                row["title"],
                row["caption"],
                platform=cfg.get("platform", "instagram"),
                cfg=cfg,
            )'''
if old_call not in src:
    print("❌ Could not find _buffer_queue_post call site")
    shutil.copy2(backup, APP); sys.exit(1)
src = src.replace(old_call, new_call, 1)
print("✅ Drain now passes cfg to _buffer_queue_post")


try:
    ast.parse(src)
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    shutil.copy2(backup, APP); sys.exit(1)

open(APP, "w", encoding="utf-8").write(src)
print()
print("=" * 60)
print("NEXT:")
print("=" * 60)
print()
print("1) Copy the whole staging-service/settings.json into Vercel's")
print("   SETTINGS_JSON env var, then redeploy")
print()
print("2) After redeploy, drain ObiEdits:")
print('   curl "https://remixmasterstaging.vercel.app/api/cron?niche=obiedits"')
print()
print("3) Expected response:")
print('   {"pushed": N, "failed": 0, "error": null, ...}')
print("   where N = number of pending ObiEdits posts")