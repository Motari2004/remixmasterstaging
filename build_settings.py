"""
Build staging-service/settings.json from:
  - remixmaster/settings.json   (Buffer niches)
  - staging-service/config.json (Zernio niches)

Result: one self-contained settings.json inside staging-service/.
Safe to re-run.
"""
import os
import sys
import json
import shutil
import datetime

HERE        = os.path.dirname(os.path.abspath(__file__))
OUT         = os.path.join(HERE, "settings.json")
CONFIG      = os.path.join(HERE, "config.json")
RM_SETTINGS = r"C:\Users\PC\Desktop\remixmaster\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def main():
    if not os.path.exists(CONFIG):
        print(f"❌ Not found: {CONFIG}"); sys.exit(1)

    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # ---- Buffer niches from remixmaster ----
    buffer_niches = {}
    if os.path.exists(RM_SETTINGS):
        with open(RM_SETTINGS, "r", encoding="utf-8") as f:
            rm = json.load(f)
        for key, v in (rm.get("NICHES") or {}).items():
            if not isinstance(v, dict):
                continue
            if (v.get("publisher") or "").lower() != "buffer":
                continue
            buffer_niches[key] = {
                "label":             v.get("label", key),
                "publisher":         "buffer",
                "platform":          (v.get("platform") or "youtube").lower(),
                "buffer_api_key":    v.get("buffer_api_key", ""),
                "buffer_channel_id": v.get("buffer_channel_id", ""),
                "channel_link":      v.get("channel_link", ""),
            }
        print(f"✅ Loaded {len(buffer_niches)} Buffer niches from remixmaster")
    else:
        print(f"⚠️  {RM_SETTINGS} not found — Buffer niches will be empty")

    # ---- Zernio niches from staging config.json ----
    zernio_niches = {}
    for key, v in (cfg.get("zernio_niches") or {}).items():
        if not isinstance(v, dict):
            continue
        zernio_niches[key] = {
            "label":             v.get("label", key),
            "publisher":         "zernio",
            "platform":          (v.get("platform") or "youtube").lower(),
            "zernio_api_key":    v.get("zernio_api_key", ""),
            "zernio_account_id": v.get("zernio_account_id", ""),
            "zernio_profile_id": v.get("zernio_profile_id", ""),
            "channel_link":      v.get("channel_link", ""),
        }
    print(f"✅ Loaded {len(zernio_niches)} Zernio niches from config.json")

    settings = {
        "NICHES": {**buffer_niches, **zernio_niches},
        "NEON_DATABASE_URL": cfg.get("neon_database_url", ""),
        "PORT":              int(cfg.get("port", 5050)),
        "_built_at":         datetime.datetime.now().isoformat(),
    }

    if os.path.exists(OUT):
        shutil.copy2(OUT, f"{OUT}.bak.{ts}")
        print(f"📦 Backup: {OUT}.bak.{ts}")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

    print(f"\n✅ Wrote: {OUT}")
    print(f"   Total niches: {len(settings['NICHES'])}")
    print(f"   Buffer:       {len(buffer_niches)}")
    print(f"   Zernio:       {len(zernio_niches)}")
    print()
    print("🎯 For Vercel, copy the contents of this file into an env")
    print("   var named SETTINGS_JSON (see README).")


if __name__ == "__main__":
    main()