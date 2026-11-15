"""
Sync made_for_kids onto every YouTube Buffer niche in the staging viewer's
settings.json, matching the pipeline's settings.json values.

- tinytoon: true  (kids content)
- everything else on YouTube: false

Only touches platform: "youtube" niches. Facebook/TikTok/Instagram untouched.
"""
import json, shutil, datetime, os

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

if not os.path.exists(SETTINGS):
    print(f"❌ Not found: {SETTINGS}")
    raise SystemExit(1)

s = json.load(open(SETTINGS, encoding="utf-8"))
shutil.copy2(SETTINGS, f"{SETTINGS}.bak.{ts}")
print(f"📦 Backup: {SETTINGS}.bak.{ts}")
print()

niches = s.get("NICHES", {})
changed = 0

for key, cfg in niches.items():
    if not isinstance(cfg, dict):
        continue
    if (cfg.get("publisher") or "").lower() != "buffer":
        continue
    if (cfg.get("platform") or "").lower() != "youtube":
        continue

    want = True if key == "tinytoon" else False
    old = cfg.get("made_for_kids")
    cfg["made_for_kids"] = want
    changed += 1
    mark = "✅" if old != want else "·"
    print(f"  {mark} {key:22s} made_for_kids: {old} → {want}")

s["NICHES"] = niches
json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2)

print()
print(f"Updated {changed} YouTube niche(s)")
print()
print("Verify:")
print(f'  python -c "import json; s=json.load(open(r\'{SETTINGS}\',encoding=\'utf-8\')); '
      f'print({{k: v.get(\'made_for_kids\') for k,v in s[\'NICHES\'].items() '
      f'if v.get(\'platform\')==\'youtube\'}})"')
print()
print("Next:")
print("  1) Copy the whole settings.json into Vercel's SETTINGS_JSON env var")
print("  2) Redeploy the remixmasterstaging project")