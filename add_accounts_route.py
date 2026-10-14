"""
Add /api/accounts route to staging-service/app.py.

Returns one row per niche with:
  label, key, publisher, platform, email, channel_id, account_id, profile_id
"""
import os, sys, shutil, datetime

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

if not os.path.exists(APP):
    print(f"❌ Not found: {APP}"); sys.exit(1)

with open(APP, "r", encoding="utf-8") as f:
    src = f.read()

shutil.copy2(APP, f"{APP}.bak.{ts}")
print(f"📦 Backup: {APP}.bak.{ts}\n")

if '@app.route("/api/accounts")' in src:
    print("ℹ️  /api/accounts already exists — nothing to do.")
    sys.exit(0)

anchor = '''@app.route("/api/log")
def api_log():
    return jsonify(success=True, rows=q_log())
'''

new_route = anchor + '''

# ---- Accounts directory ----
@app.route("/api/accounts")
def api_accounts():
    """One row per niche with its workspace email + channel identifiers."""
    rows = []
    for key, cfg in NICHES.items():
        if not isinstance(cfg, dict):
            continue
        publisher = (cfg.get("publisher") or "").lower()
        api_key = cfg.get("buffer_api_key") or cfg.get("zernio_api_key") or ""
        rows.append({
            "key":          key,
            "label":        cfg.get("label", key),
            "publisher":    publisher,
            "platform":     (cfg.get("platform") or "").lower(),
            "email":        cfg.get("email") or "",
            "channel_id":   cfg.get("buffer_channel_id") or "",
            "account_id":   cfg.get("zernio_account_id") or "",
            "profile_id":   cfg.get("zernio_profile_id") or "",
            "channel_link": cfg.get("channel_link") or "",
            "api_key_hint": (api_key[:10] + "…") if api_key else "",
        })
    rows.sort(key=lambda r: (r["email"] == "", r["email"], r["label"].lower()))
    return jsonify(success=True, rows=rows)
'''

if anchor not in src:
    print("❌ Could not find /api/log anchor in app.py")
    print('   Run: findstr /N /C:"api/log" app.py')
    sys.exit(1)

src = src.replace(anchor, new_route, 1)

with open(APP, "w", encoding="utf-8") as f:
    f.write(src)

print("✅ /api/accounts route added to app.py")
print(f"\n✅ Wrote: {APP}")
print(f"📦 Backup: {APP}.bak.{ts}")
print()
print("Verify syntax with:")
print('  python -c "import ast; ast.parse(open(\'app.py\',encoding=\'utf-8\').read()); print(\'syntax OK\')"')