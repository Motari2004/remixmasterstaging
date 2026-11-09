"""
Add 'gaminghub' (Apex Gaming Hub, Facebook Reel via Buffer) to
staging-service/settings.json so the Vercel viewer sees it.
"""
import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}")
print()

niches = s.setdefault("NICHES", {})

niches["gaminghub"] = {
    "label":             "Apex Gaming Hub",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "z9iuwGg_xJY5X8sihQOqVX-VRYUYYeEkZ_-DQVZAu0F",
    "buffer_channel_id": "6af1b46c62b70b94b0ce9a6c",
    "channel_link":      "",
    "email":             "",
}

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2)
print("✅ Added gaminghub to viewer settings.json")
print(f"   Total NICHES: {len(niches)}")
print()
print("Next: copy the ENTIRE settings.json into Vercel's SETTINGS_JSON")
print("env var, then redeploy.")