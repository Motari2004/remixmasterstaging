import datetime
import json
import shutil

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})

niches["worldwonders"] = {
    "label":             "Wild Wonders",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "59P6QgJrq40-fFDX39VAuyfRSocNp1QR3wDwFA4ag7C",
    "buffer_channel_id": "6b094f6c8541f09ecbbf44df",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["worldwonders"] = ["worldwonders"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added worldwonders to staging-service/settings.json")
print("   Channel ID: 6b094f6c8541f09ecbbf44df")
print("   Total NICHES: {}".format(len(niches)))