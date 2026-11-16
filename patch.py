"""
Minimal, crash-proof patch for staging-service/settings.json.

Adds 'moonlightoons' to NICHES and NICHE_GROUPS by string surgery on the
raw JSON text. Does NOT round-trip through json.load/json.dump, so no
TypeError: set is not JSON serializable.

Atomic: writes to .tmp, validates with json.load, then replaces.
Backup on failure.
"""
import os, sys, json, shutil, datetime

SETTINGS = r"C:\Users\PC\Desktop\staging-service\settings.json"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

if not os.path.exists(SETTINGS):
    print(f"Not found: {SETTINGS}")
    sys.exit(1)

with open(SETTINGS, "r", encoding="utf-8") as f:
    src = f.read()

backup = f"{SETTINGS}.bak.{ts}"
shutil.copy2(SETTINGS, backup)
print(f"Backup: {backup}")
print()

# ---- 1. Add 'moonlightoons' to NICHES (before the closing of the NICHES dict) ----
NICHE_ENTRY = ''',
    "moonlightoons": {
      "label": "Moonlightoons",
      "publisher": "buffer",
      "platform": "instagram",
      "buffer_api_key": "Gjyl_FWtZTSbFmMZvDip8_kbQD69pJr4qIRoZoOJCZN",
      "buffer_channel_id": "6afb0bdeece6dfde5fe4812c",
      "channel_link": "",
      "email": ""
    }'''

if '"moonlightoons"' in src:
    print("NICHES: 'moonlightoons' already present - skipping insert")
else:
    # Find the end of the NICHES object: the first '\n  },\n  "' after '"NICHES": {'
    niche_start = src.find('"NICHES": {')
    if niche_start == -1:
        print("ERROR: Could not find '\"NICHES\": {' in file")
        shutil.copy2(backup, SETTINGS)
        sys.exit(1)

    # Walk forward, tracking brace depth of the NICHES object only
    depth = 0
    in_str = False
    escape = False
    niche_close = -1
    i = src.find('{', niche_start)  # opening { of NICHES
    for j in range(i, len(src)):
        c = src[j]
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                niche_close = j
                break

    if niche_close == -1:
        print("ERROR: Could not find closing '}' of NICHES")
        shutil.copy2(backup, SETTINGS)
        sys.exit(1)

    # Insert before that '}'. Need to find the last comma already in NICHES
    # so our insertion has a preceding comma. Find the last non-whitespace
    # char before niche_close.
    k = niche_close - 1
    while k > 0 and src[k] in " \t\r\n":
        k -= 1

    if src[k] == ',':
        # Already has trailing comma — our block starts with ',' which would double it
        new_block = NICHE_ENTRY.replace(',\n    "moonlightoons"', '\n    "moonlightoons"', 1)
    else:
        new_block = NICHE_ENTRY

    src = src[:niche_close] + new_block + "\n  " + src[niche_close:]
    print("NICHES: inserted 'moonlightoons'")


# ---- 2. Add 'moonlightoons' to NICHE_GROUPS ----
GROUP_ENTRY = ''',
    "moonlightoons": [
      "moonlightoons"
    ]'''

if '"NICHE_GROUPS"' not in src:
    # No NICHE_GROUPS object at all — add it before the final '}'
    if '"moonlightoons"' not in src.split('"NICHE_GROUPS"')[0]:
        # safer: just append a NICHE_GROUPS block before the last '}'
        pass  # we'll handle below
    # Find last '}' at column 0-ish (end of top-level object)
    last = src.rfind('}')
    if last == -1:
        print("ERROR: no closing '}' in file")
        shutil.copy2(backup, SETTINGS)
        sys.exit(1)
    k = last - 1
    while k > 0 and src[k] in " \t\r\n":
        k -= 1
    prefix = "" if src[k] == ',' else ","
    src = src[:k+1] + prefix + '\n  "NICHE_GROUPS": {\n    "moonlightoons": ["moonlightoons"]\n  }' + src[last:]
    print("NICHE_GROUPS: created with 'moonlightoons'")
else:
    # NICHE_GROUPS exists — find its closing brace and insert before it
    gstart = src.find('"NICHE_GROUPS": {')
    gopen = src.find('{', gstart)
    depth = 0
    in_str = False
    escape = False
    gclose = -1
    for j in range(gopen, len(src)):
        c = src[j]
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                gclose = j
                break

    if gclose == -1:
        print("ERROR: could not find closing '}' of NICHE_GROUPS")
        shutil.copy2(backup, SETTINGS)
        sys.exit(1)

    # Only insert if 'moonlightoons' is not already a group key
    body = src[gopen:gclose]
    if '"moonlightoons"' in body:
        print("NICHE_GROUPS: 'moonlightoons' already present - skipping insert")
    else:
        k = gclose - 1
        while k > 0 and src[k] in " \t\r\n":
            k -= 1
        if src[k] == ',':
            new_block = GROUP_ENTRY.replace(',\n    "moonlightoons"', '\n    "moonlightoons"', 1)
        else:
            new_block = GROUP_ENTRY
        src = src[:gclose] + new_block + "\n  " + src[gclose:]
        print("NICHE_GROUPS: inserted 'moonlightoons'")


# ---- 3. Validate + write ----
try:
    json.loads(src)  # <-- pure string parse, no json.dump
except json.JSONDecodeError as e:
    print(f"Resulting JSON is invalid: {e}")
    print(f"Restoring backup {backup}")
    shutil.copy2(backup, SETTINGS)
    sys.exit(1)

tmp = SETTINGS + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    f.write(src)

os.replace(tmp, SETTINGS)

print()
print("Done. Verify:")
print('  python -c "import json; s=json.load(open(\'settings.json\')); '
      'print(\'moonlightoons\' in s[\'NICHES\'], \'moonlightoons\' in s.get(\'NICHE_GROUPS\', {}))"')