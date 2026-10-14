"""
Populate settings.json with the correct 'email' per niche.

Buffer workspaces discovered by querying `account { email }` for each key.
Zernio doesn't expose email via API — those get a placeholder.
"""
import os, sys, json, shutil, datetime
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(HERE, "settings.json")
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def buffer_email(api_key):
    """Return the email that owns a Buffer API key, or None."""
    try:
        r = requests.post(
            "https://api.buffer.com",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"query": "{ account { id email name } }"},
            timeout=15,
        )
        if not r.ok:
            return None
        data = r.json().get("data", {})
        return (data.get("account") or {}).get("email")
    except Exception:
        return None


def main():
    if not os.path.exists(SETTINGS_FILE):
        print(f"❌ Not found: {SETTINGS_FILE}"); sys.exit(1)

    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        s = json.load(f)

    niches = s.get("NICHES", {})
    if not isinstance(niches, dict):
        print("❌ NICHES block missing or malformed"); sys.exit(1)

    shutil.copy2(SETTINGS_FILE, f"{SETTINGS_FILE}.bak.{ts}")
    print(f"📦 Backup: {SETTINGS_FILE}.bak.{ts}\n")

    # Cache emails per API key so we only call Buffer once per workspace
    email_cache = {}
    updated = 0

    for key, cfg in niches.items():
        if not isinstance(cfg, dict):
            continue
        publisher = (cfg.get("publisher") or "").lower()

        if publisher == "buffer":
            api_key = (cfg.get("buffer_api_key")
                       or s.get("BUFFER_API_KEY") or "").strip()
            if not api_key:
                print(f"  ⚠️  {key}: no buffer_api_key")
                continue
            if api_key not in email_cache:
                email_cache[api_key] = buffer_email(api_key)
            email = email_cache[api_key]
            if email:
                cfg["email"] = email
                updated += 1
                print(f"  ✅ {key:24s} {email}")
            else:
                print(f"  ❌ {key}: could not fetch Buffer email")

        elif publisher == "zernio":
            # Zernio doesn't expose email — leave placeholder so the tab
            # visibly flags it as "not set"
            if not cfg.get("email"):
                cfg["email"] = ""
                print(f"  ⚠️  {key:24s} (Zernio — set manually)")

    s["NICHES"] = niches

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)

    print(f"\n✅ Updated {updated} Buffer niche(s) with email")
    print(f"📦 Backup: {SETTINGS_FILE}.bak.{ts}")
    print()
    print("Next: fill in the Zernio emails manually.")
    print("   Open settings.json and set the 'email' field for each zernio niche.")


if __name__ == "__main__":
    main()