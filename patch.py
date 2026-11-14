import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}")

niches = s.setdefault("NICHES", {})
niches["cjtiktok"] = {
    "label":             "cjhood8 (TikTok)",
    "publisher":         "buffer",
    "platform":          "tiktok",
    "buffer_api_key":    "z9iuwGg_xJY5X8sihQOqVX-VRYUYYeEkZ_-DQVZAu0F",
    "buffer_channel_id": "6af81cc062b70b94b02a1b56",
    "channel_link":      "",
    "email":             "s.corpioguardian1@gmail.com",
}
json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2)
print("✅ Added cjtiktok to viewer settings.json")