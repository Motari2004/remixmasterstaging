import os, sys, json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

with open(SETTINGS, "r", encoding="utf-8") as f:
    s = json.load(f)

shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}")

niches = s.setdefault("NICHES", {})
niches["humorhub"] = {
    "label":             "Humor Hub",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "axPwy0r1QJlQWPZ28LaPKrHVfnKXvC3jw3f_ft-oGRs",
    "buffer_channel_id": "6af055f162b70b94b0bcd7b6",
    "channel_link":      "",
    "email":             "",
}

with open(SETTINGS, "w", encoding="utf-8") as f:
    json.dump(s, f, indent=2)

print("✅ Added 'humorhub' to viewer settings.json")
print()
print("Next: copy the WHOLE settings.json into the Vercel SETTINGS_JSON")
print("      env var, then redeploy.")