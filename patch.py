import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})

niches["bmwlife"] = {
    "label":             "Bmw-Life",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "iKP6jMSBVtG9hdP5rJHHfutQ-BVrYYaXYx6qrSpxE6E",
    "buffer_channel_id": "6afd78b1ece6dfde5f08cc03",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["bmwlife"] = ["bmwlife"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added bmwlife (Facebook, BMW page) to staging-service/settings.json")
print("   Channel ID: 6afd78b1ece6dfde5f08cc03")
print("   Total NICHES: {}".format(len(niches)))