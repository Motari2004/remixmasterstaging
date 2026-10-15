"""
Add MindsetFuel.KE to staging-service/settings.json.
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
niches["mindsetfuelke"] = {
    "label":             "MindsetFuel.KE",
    "publisher":         "buffer",
    "platform":          "tiktok",
    "buffer_api_key":    "rxbG2e0wUwQ1GbYmS85Ru7IUet08sbp6MmcIkrB_aMc",
    "buffer_channel_id": "6ad150bd778b240e2f1fd4e5",
    "email":             "freelancer16594@gmail.com",
    "channel_link":      "",
}
print("✅ NICHES.mindsetfuelke added")

with open(SETTINGS, "w", encoding="utf-8") as f:
    json.dump(s, f, indent=2)

print(f"\n✅ Wrote: {SETTINGS}")