import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})

niches["carljohnson"] = {
    "label":             "Carl Johnson",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "qXcN6Rs42vqOM8sMDou8YpX_XmlFKwdEfos6J3D52jC",
    "buffer_channel_id": "6b068dec8541f09ecb994d2a",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["carljohnson"] = ["carljohnson"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added carljohnson to staging-service/settings.json")
print("   Total NICHES: {}".format(len(niches)))