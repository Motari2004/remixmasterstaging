"""
Add 'specialforces' to staging-service/settings.json.
"""
import os, sys, json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

if not os.path.exists(SETTINGS):
    print(f"❌ Not found: {SETTINGS}"); sys.exit(1)

with open(SETTINGS, "r", encoding="utf-8") as f:
    s = json.load(f)

shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}\n")

niches = s.setdefault("NICHES", {})
niches["specialforces"] = {
    "label":             "Special Forces",
    "publisher":         "buffer",
    "platform":          "tiktok",
    "buffer_api_key":    "4g4jAWbNExouL9F9gpGpWaQhZq6kY4H3EYzEHE7t5Qh",
    "buffer_channel_id": "6ad1e268778b240e2f26ad16",
    "email":             "johnsmark059@gmail.com",
    "channel_link":      "",
}
print("✅ NICHES.specialforces added")

with open(SETTINGS, "w", encoding="utf-8") as f:
    json.dump(s, f, indent=2)

print(f"\n✅ Wrote: {SETTINGS}")