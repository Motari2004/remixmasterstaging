import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}")

niches = s.setdefault("NICHES", {})

niches["funnyclips401"] = {
    "label":             "Funny Clips 401",
    "publisher":         "buffer",
    "platform":          "instagram",
    "buffer_api_key":    "Gjyl_FWtZTSbFmMZvDip8_kbQD69pJr4qIRoZoOJCZN",
    "buffer_channel_id": "6afc819dece6dfde5ffa0357",
    "channel_link":      "",              # empty → validator won't require link in output
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["funnyclips401"] = ["funnyclips401"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added funnyclips401 (Instagram, new key) to staging-service/settings.json")
print(f"   Channel ID: 6afc819dece6dfde5ffa0357")
print(f"   Total NICHES: {len(niches)}")