import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})

niches["luxuryhousepoint"] = {
    "label":             "Luxuryhousepoint",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "dm4WswE8Clc1_7iMW4rkm3CEWOwYqlaK7k3QBIr9RxR",
    "buffer_channel_id": "6afe927dece6dfde5f19d9fb",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["luxuryhousepoint"] = ["luxuryhousepoint"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added luxuryhousepoint (Facebook) to staging-service/settings.json")
print("   Channel ID: 6afe927dece6dfde5f19d9fb")
print("   Total NICHES: {}".format(len(niches)))