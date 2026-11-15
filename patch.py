import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}")

niches = s.setdefault("NICHES", {})
niches["mentalistedits"] = {
    "label":             "Mentalist Edits (TikTok)",
    "publisher":         "buffer",
    "platform":          "tiktok",
    "buffer_api_key":    "8Wqb-YUhRLP7pNq62o6Z8IfoM9n1dtY0ctIOuUGBjPu",
    "buffer_channel_id": "6af96dabece6dfde5fcf75de",
    "channel_link":      "",
    "email":             "freelancer16594@gmail.com",
}
json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2)
print("✅ Added mentalistedits to viewer settings.json")
print(f"   Total NICHES: {len(niches)}")