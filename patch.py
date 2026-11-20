import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})

niches["lyricvibe"] = {
    "label":             "lyricvibe",
    "publisher":         "buffer",
    "platform":          "youtube",
    "buffer_api_key":    "AS4xWvk_XpQrOIsDjXvKh9Ju_3bPcUEP3oP0caUda6m",
    "buffer_channel_id": "6aff24e5ece6dfde5f2129b4",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["lyricvibe"] = ["lyricvibe"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added lyricvibe (YouTube) to staging-service/settings.json")
print("   Channel ID: 6aff24e5ece6dfde5f2129b4")
print("   Total NICHES: {}".format(len(niches)))