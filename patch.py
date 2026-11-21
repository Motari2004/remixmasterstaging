import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})

niches["militarydrills"] = {
    "label":             "Military Drills",
    "publisher":         "buffer",
    "platform":          "youtube",
    "buffer_api_key":    "YejnMy656UwVGgapzVDWIIkB0JszNCzu7iExNEpNiJ6",
    "buffer_channel_id": "6b0131a4ece6dfde5f3fd9f0",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["militarydrills"] = ["militarydrills"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added militarydrills (YouTube) to staging-service/settings.json")
print("   Channel ID: 6b0131a4ece6dfde5f3fd9f0")
print("   Total NICHES: {}".format(len(niches)))