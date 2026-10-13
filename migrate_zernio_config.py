"""
Copy every Zernio niche from remixmaster/settings.json into the
staging-service's own config.json under "zernio_niches".

Run once. Safe to re-run — it re-copies the latest values.
"""
import os
import sys
import json
import shutil
import datetime

HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG      = os.path.join(HERE, "config.json")
RM_SETTINGS = r"C:\Users\PC\Desktop\remixmaster\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def main():
    if not os.path.exists(CONFIG):
        print(f"❌ Not found: {CONFIG}"); sys.exit(1)
    if not os.path.exists(RM_SETTINGS):
        print(f"❌ Not found: {RM_SETTINGS}"); sys.exit(1)

    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    with open(RM_SETTINGS, "r", encoding="utf-8") as f:
        rm = json.load(f)

    rm_niches = rm.get("NICHES", {})
    zernio = {}
    for key, v in rm_niches.items():
        if not isinstance(v, dict):
            continue
        if (v.get("publisher") or "").lower() != "zernio":
            continue
        zernio[key] = {
            "label":             v.get("label", key),
            "zernio_api_key":    (v.get("zernio_api_key")
                                  or rm.get("ZERNIO_API_KEY") or "").strip(),
            "zernio_account_id": (v.get("zernio_account_id") or "").strip(),
            "zernio_profile_id": (v.get("zernio_profile_id") or "").strip(),
            "platform":          (v.get("platform") or "youtube").lower(),
            "channel_link":      v.get("channel_link", ""),
        }

    if not zernio:
        print("⚠️  No Zernio niches found in remixmaster settings.json."); sys.exit(1)

    shutil.copy2(CONFIG, f"{CONFIG}.bak.{ts}")
    print(f"📦 Backup: {CONFIG}.bak.{ts}\n")

    cfg["zernio_niches"] = zernio
    cfg.pop("remixmaster_settings", None)   # no longer needed

    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    print(f"✅ Copied {len(zernio)} Zernio niche(s) into config.json")
    for k, v in zernio.items():
        print(f"   - {k}: {v['label']}  profile={v['zernio_profile_id'][:12]}…")
    print()
    print("✅ Removed remixmaster_settings pointer from config.json")
    print()
    print("🎯 Next: overwrite zernio_client.py and app.py, then restart")


if __name__ == "__main__":
    main()