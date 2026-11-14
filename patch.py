import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")

niches = s.setdefault("NICHES", {})
niches["obiedits"] = {
    "label":              "ObiEdits (YouTube)",
    "publisher":          "buffer",
    "platform":           "youtube",
    "buffer_api_key":     "2axk9s7YibSoMTsebkHZQaEKQCTDly75b2Np4F8gJnI",
    "buffer_channel_id":  "6af8b52f62b70b94b031eb57",
    "channel_link":       "",
    "email":              "h.opefreymosingi1@gmail.com",
    "max_output_seconds": 60,
}
json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2)
print("✅ Added obiedits to viewer settings.json")