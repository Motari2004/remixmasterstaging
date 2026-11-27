import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})

niches["aripvlogger"] = {
    "label":             "Arip Vlogger",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "59P6QgJrq40-fFDX39VAuyfRSocNp1QR3wDwFA4ag7C",
    "buffer_channel_id": "6b0932708541f09ecbbe0bf7",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["aripvlogger"] = ["aripvlogger"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added aripvlogger to staging-service/settings.json")
print("   Channel ID: 6b0932708541f09ecbbe0bf7")
print("   Total NICHES: {}".format(len(niches)))