import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}")

niches = s.setdefault("NICHES", {})
niches["obiyang09"] = {
    "label":             "obiyang09",
    "publisher":         "buffer",
    "platform":          "tiktok",
    "buffer_api_key":    "9w4eStTWQwYxHm7fHVXZxK29ZF2H9m8KRa5NhgJJ6ht",
    "buffer_channel_id": "6af9be3bece6dfde5fd2af3f",
    "channel_link":      "https://www.tiktok.com/@obiyang09",
    "email":             "coreiq04@gmail.com",
}
json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2)
print("✅ Added obiyang09 to settings.json")
print(f"   Total NICHES: {len(niches)}")