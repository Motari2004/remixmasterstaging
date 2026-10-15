"""
Add SmartMind Studios to staging-service/settings.json.
Same channel + key as remixmaster.
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

niches["smartmindstudios"] = {
    "label":             "SmartMind Studios",
    "publisher":         "buffer",
    "platform":          "youtube",
    "buffer_api_key":    "-wImCowUrU14yxbE-eNOvSImWU-MFh9PyqKJwnsTEI8",
    "buffer_channel_id": "6ad10287778b240e2f1b0f2a",
    "email":             "smartmind006@gmail.com",
    "channel_link":      "",
}
print("✅ NICHES.smartmindstudios added")

if "cinemaclips37" in niches:
    niches["cinemaclips37"]["platform"] = "tiktok"
    niches["cinemaclips37"].setdefault("email", "smartmind006@gmail.com")
    print("✅ cinemaclips37 → tiktok")

if "tinytoon" in niches:
    niches["tinytoon"].setdefault("email", "smartmind006@gmail.com")
    print("✅ tinytoon email set")

with open(SETTINGS, "w", encoding="utf-8") as f:
    json.dump(s, f, indent=2)

print(f"\n✅ Wrote: {SETTINGS}")