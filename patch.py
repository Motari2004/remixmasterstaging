"""
Add 'comedyreels' to staging-service/settings.json for the Vercel viewer.
"""
import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}")

niches = s.setdefault("NICHES", {})
niches["comedyreels"] = {
    "label":             "Comedy Reels",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "6vWoDkYI1k8pLVLtBlpjIPmkrXEja4berTuXb8WCyO5",
    "buffer_channel_id": "6af5fd2662b70b94b00b7ac0",
    "channel_link":      "",
    "email":             "s.martmind006@gmail.com",
}

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2)
print("✅ Added comedyreels to viewer settings.json")
print(f"   Total NICHES: {len(niches)}")