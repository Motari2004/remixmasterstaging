import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}")

niches = s.setdefault("NICHES", {})

niches["unfiltered201"] = {
    "label":             "unfil_tered201",
    "publisher":         "buffer",
    "platform":          "instagram",
    "buffer_api_key":    "iKP6jMSBVtG9hdP5rJHHfutQ-BVrYYaXYx6qrSpxE6E",
    "buffer_channel_id": "6afcbc58ece6dfde5ffe07f8",
    "channel_link":      "",
    "email":             "",
}

groups = s.setdefault("NICHE_GROUPS", {})
groups["unfiltered201"] = ["unfiltered201"]

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("✅ Added unfiltered201 (Instagram, iKP6 key) to staging-service/settings.json")
print(f"   Channel ID: 6afcbc58ece6dfde5ffe07f8")
print(f"   Total NICHES: {len(niches)}")