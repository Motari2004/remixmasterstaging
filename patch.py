import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})

niches["kingsedts"] = {
    "label":             "Kings Edts Official",
    "publisher":         "buffer",
    "platform":          "youtube",
    "buffer_api_key":    "6vWoDkYI1k8pLVLtBlpjIPmkrXEja4berTuXb8WCyO5",
    "buffer_channel_id": "6b014ab2ece6dfde5f411cb5",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["kingsedts"] = ["kingsedts"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added kingsedts (YouTube) to staging-service/settings.json")
print("   Channel ID: 6b014ab2ece6dfde5f411cb5")
print("   Total NICHES: {}".format(len(niches)))