import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}")

niches = s.setdefault("NICHES", {})
niches["funnyclips201"] = {
    "label":             "Funny Clips 201",
    "publisher":         "buffer",
    "platform":          "instagram",
    "buffer_api_key":    "9w4eStTWQwYxHm7fHVXZxK29ZF2H9m8KRa5NhgJJ6ht",
    "buffer_channel_id": "6afac17bece6dfde5fe1688f",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["funnyclips201"] = ["funnyclips201"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2)
print("✅ Added funnyclips201 to settings.json")
print(f"   Total NICHES: {len(niches)}")