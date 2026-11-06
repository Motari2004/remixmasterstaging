"""
Add 'hahahub' (Ha Ha Hub, Facebook Reel) to staging-service/settings.json
so the Vercel viewer sees it.

This file is the viewer's copy. The pipeline's copy at
remixmaster/settings.json also needs the entry — separate patch.
"""
import os, sys, json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

if not os.path.exists(SETTINGS):
    print(f"❌ Not found: {SETTINGS}"); sys.exit(1)

with open(SETTINGS, "r", encoding="utf-8") as f:
    s = json.load(f)

shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}\n")

niches = s.setdefault("NICHES", {})

HAHAHUB = {
    "label":             "Ha Ha Hub",
    "publisher":         "buffer",
    "platform":          "facebook",
    "buffer_api_key":    "9w4eStTWQwYxHm7fHVXZxK29ZF2H9m8KRa5NhgJJ6ht",
    "buffer_channel_id": "6aedb7cfe29c69a1718044ae",
    "channel_link":      "",
    "email":             "",
}

if "hahahub" in niches:
    print("ℹ️  hahahub already present — refreshing values")
else:
    print("✅ Adding hahahub")

niches["hahahub"] = HAHAHUB

with open(SETTINGS, "w", encoding="utf-8") as f:
    json.dump(s, f, indent=2)

print()
print(f"✅ Wrote {SETTINGS}")
print(f"   NICHES count: {len(niches)}")
print()
print("Next:")
print("  1) Rebuild the SETTINGS_JSON env var for Vercel:")
print("     Copy the contents of this file into the env var named SETTINGS_JSON")
print("     in the Vercel project, then redeploy.")
print("  2) For local viewer testing:")
print("     cd C:\\Users\\PC\\Desktop\\staging-service")
print("     python app.py")
print("  3) For the pipeline to actually publish hahahub:")
print("     Add the same entry to remixmaster/settings.json too")
print("     (use C:\\Users\\PC\\Desktop\\remixmaster\\add_hahahub_niche.py)")