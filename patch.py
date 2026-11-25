import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})

niches["movieshub"] = {
    "label":             "Movies Hub",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "NZUkWuR4CFUAc-hPK9umuLz7_gViJNFP8695PeJdPjb",
    "buffer_channel_id": "6b069f438541f09ecb9a1a7a",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["movieshub"] = ["movieshub"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added movieshub to staging-service/settings.json")
print("   Channel ID: 6b069f438541f09ecb9a1a7a")
print("   Total NICHES: {}".format(len(niches)))