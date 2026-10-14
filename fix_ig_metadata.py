"""
Add platform-aware metadata to the createPost mutation.

Buffer requires platform-specific metadata:
  - Instagram: type (reel), shouldShareToFeed (true)
  - Facebook : type (reel)
  - TikTok   : none
  - YouTube  : title, privacy

For now we handle Instagram explicitly and pass a minimal default
for other platforms — which is what remixmaster's buffer.py does.
"""
import os, sys, shutil, datetime

APP = r"C:\Users\PC\Desktop\staging-service\app.py"
ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

if not os.path.exists(APP):
    print(f"❌ Not found: {APP}"); sys.exit(1)

with open(APP, "r", encoding="utf-8") as f:
    src = f.read()

shutil.copy2(APP, f"{APP}.bak.{ts}")
print(f"📦 Backup: {APP}.bak.{ts}\n")

# ---- 1. Extend _buffer_queue_post signature to accept platform ----
old_sig = "def _buffer_queue_post(api_key, channel_id, video_url, title, caption):"
new_sig = "def _buffer_queue_post(api_key, channel_id, video_url, title, caption, platform=\"instagram\"):"

if old_sig not in src:
    print("❌ Could not find _buffer_queue_post signature"); sys.exit(1)
src = src.replace(old_sig, new_sig, 1)
print("✅ Signature now accepts platform")

# ---- 2. Build the metadata block per platform ----
old_vars = '''    variables = {
        "input": {
            "channelId": channel_id,
            "text": text,
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "assets": [{"video": {"url": video_url}}],
        }
    }'''

new_vars = '''    # ---- platform-specific metadata ----
    # Buffer requires certain fields depending on the channel's platform.
    # Instagram needs `type` and `shouldShareToFeed`. Facebook needs `type`.
    # TikTok/YouTube accept the post without extra metadata in this shape.
    plat = (platform or "").lower()
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
    # tiktok / youtube / others: no metadata block

    variables = {
        "input": {
            "channelId": channel_id,
            "text": text,
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "assets": [{"video": {"url": video_url}}],
        }
    }
    if metadata:
        variables["input"]["metadata"] = metadata'''

if old_vars not in src:
    print("❌ Could not find variables block"); sys.exit(1)
src = src.replace(old_vars, new_vars, 1)
print("✅ Metadata block added (instagram/facebook handled)")

# ---- 3. Pass platform from _drain_niche ----
old_call = '''            bid = _buffer_queue_post(
                api_key,
                channel_id,
                row["video_url"],
                row["title"],
                row["caption"],
            )'''

new_call = '''            bid = _buffer_queue_post(
                api_key,
                channel_id,
                row["video_url"],
                row["title"],
                row["caption"],
                platform=cfg.get("platform", "instagram"),
            )'''

if old_call not in src:
    print("❌ Could not find _buffer_queue_post call site"); sys.exit(1)
src = src.replace(old_call, new_call, 1)
print("✅ Drain passes platform through")

with open(APP, "w", encoding="utf-8") as f:
    f.write(src)

print(f"\n✅ Wrote: {APP}")
print(f"📦 Backup: {APP}.bak.{ts}")
print()
print("🎯 Verify syntax:")
print('   python -c "import ast; ast.parse(open(\'app.py\',encoding=\'utf-8\').read()); print(\'syntax OK\')"')
print()
print("🎯 Then:")
print("   git add app.py .gitignore")
print('   git commit -m "add platform metadata to Buffer createPost"')
print("   git push origin main")