import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})

niches["funnydaily"] = {
    "label":             "Funny Daily",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "qXcN6Rs42vqOM8sMDou8YpX_XmlFKwdEfos6J3D52jC",
    "buffer_channel_id": "6b0470728541f09ecb78eb73",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["funnydaily"] = ["funnydaily"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added funnydaily (facebook) to staging-service/settings.json")
print("   Channel ID: 6b0470728541f09ecb78eb73")
print("   Total NICHES: {}".format(len(niches)))