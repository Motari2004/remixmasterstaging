import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})

niches["reggaevault"] = {
    "label":             "Reggae Vault",
    "publisher":         "buffer",
    "platform":          "youtube",
    "buffer_api_key":    "cJ_1Tg-A5URRltLJZZc1k5zvl3gXI7_t7k6CxPQGcKf",
    "buffer_channel_id": "6b03531e8541f09ecb69deb6",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["reggaevault"] = ["reggaevault"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added reggaevault (YouTube) to staging-service/settings.json")
print("   Channel ID: 6b03531e8541f09ecb69deb6")
print("   Total NICHES: {}".format(len(niches)))