import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})

niches["hongfan"] = {
    "label":             "Hong Fan",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "0JjexI8exlYOQ33y-YnzScNJJusSFdtAPLhLPYgdkF7",
    "buffer_channel_id": "6b02cedb8541f09ecb627ad8",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["hongfan"] = ["hongfan"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added hongfan (Facebook) to staging-service/settings.json")
print("   Channel ID: 6b02cedb8541f09ecb627ad8")
print("   Total NICHES: {}".format(len(niches)))