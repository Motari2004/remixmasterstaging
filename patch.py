import datetime
import json
import os
import shutil

SETTINGS_PATH = r"C:\Users\PC\Desktop\staging-service\settings.json"

KEY          = "funnycomedy"
LABEL        = "Funny Comedy"
PLATFORM     = "facebook"
PUBLISHER    = "buffer"
API_KEY      = "NZUkWuR4CFUAc-hPK9umuLz7_gViJNFP8695PeJdPjb"
CHANNEL_ID   = "6b07f2328541f09ecbacb5c4"
CHANNEL_LINK = ""
EMAIL        = ""


def main() -> None:
    if not os.path.exists(SETTINGS_PATH):
        print(f"❌ settings.json not found: {SETTINGS_PATH}")
        raise SystemExit(1)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{SETTINGS_PATH}.bak.{ts}"
    shutil.copy2(SETTINGS_PATH, backup_path)
    print(f"📦 Backed up settings.json -> {backup_path}")

    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    niches = data.setdefault("NICHES", {})
    niches[KEY] = {
        "label": LABEL,
        "publisher": PUBLISHER,
        "platform": PLATFORM,
        "buffer_api_key": API_KEY,
        "buffer_channel_id": CHANNEL_ID,
        "channel_link": CHANNEL_LINK,
        "email": EMAIL,
    }

    groups = data.setdefault("NICHE_GROUPS", {})
    groups[KEY] = [KEY]

    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Patched staging settings.json: '{KEY}' ({PLATFORM}) -> {CHANNEL_ID}")


if __name__ == "__main__":
    main()