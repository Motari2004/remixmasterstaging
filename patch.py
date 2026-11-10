"""
Add 'laughclubdaily' to staging-service/settings.json so the viewer sees it.
"""
import json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}")

niches = s.setdefault("NICHES", {})
niches["laughclubdaily"] = {
    "label":             "Laugh Club Daily",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "2axk9s7YibSoMTsebkHZQaEKQCTDly75b2Np4F8gJnI",
    "buffer_channel_id": "6af2f67d62b70b94b0e08d35",
    "channel_link":      "",
    "email":             "",
}

json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2)
print("✅ Added laughclubdaily to viewer settings.json")
print()
print("Next: copy the WHOLE settings.json into Vercel's SETTINGS_JSON env var,")
print("then redeploy the remixmasterstaging project.")