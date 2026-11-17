import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}")

niches = s.setdefault("NICHES", {})

niches["mrvibeman1"] = {
    "label":             "mrvibeman_1",
    "publisher":         "buffer",
    "platform":          "instagram",
    "buffer_api_key":    "Gjyl_FWtZTSbFmMZvDip8_kbQD69pJr4qIRoZoOJCZN",
    "buffer_channel_id": "6afcac04ece6dfde5ffd2856",
    "channel_link":      "",              # empty → validator won't require link in output
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["mrvibeman1"] = ["mrvibeman1"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added mrvibeman1 (Instagram, Gjyl key) to staging-service/settings.json")
print(f"   Channel ID: 6afcac04ece6dfde5ffd2856")
print(f"   Total NICHES: {len(niches)}")