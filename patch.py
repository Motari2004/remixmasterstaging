import json, shutil, datetime, os

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

KEY        = "ringsidestories"
LABEL      = "Ringside Stories"
API_KEY    = "DAnB91pjBYZbbMY6RUjq2qr1rashKQ4WKnOlrRaSteP"
CHANNEL_ID = "6b020945ece6dfde5f4b2c08"

if not os.path.exists(SETTINGS):
    print("❌ Not found: {}".format(SETTINGS))
    print("   Fix the SETTINGS path at the top of this script.")
    raise SystemExit(1)

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, "{}.bak.{}".format(SETTINGS, ts))
print("📦 Backup: {}.bak.{}".format(SETTINGS, ts))

niches = s.setdefault("NICHES", {})
groups = s.setdefault("NICHE_GROUPS", {})

niches[KEY] = {
    "label":             LABEL,
    "publisher":         "buffer",
    "platform":          "youtube",
    "buffer_api_key":    API_KEY,
    "buffer_channel_id": CHANNEL_ID,
    "channel_link":      "",
    "email":             "",
}
groups[KEY] = [KEY]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("✅ staging settings.json: {} (youtube) -> {}".format(KEY, CHANNEL_ID))
print("   Total NICHES: {}".format(len(niches)))