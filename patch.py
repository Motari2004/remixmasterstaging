"""
Add staged-queue deletion to staging-service/app.py.

The delete helpers go INTO app.py (not db.py) because app.py defines
q_queue / conn / etc. inline and does not import db.

Anchor: @app.route("/api/queue/<niche>") — the existing read route.
New routes are inserted immediately after it.
"""
import os, sys, shutil, datetime, ast

APP = r"C:\Users\PC\Desktop\staging-service\app.py"
ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

if not os.path.exists(APP):
    print(f"❌ Not found: {APP}"); sys.exit(1)

src = open(APP, encoding="utf-8").read()
backup = f"{APP}.bak.{ts}"
shutil.copy2(APP, backup)
print(f"📦 Backup: {backup}")

if "/api/staged/" in src:
    print("·  staged delete routes already present — nothing to do")
    sys.exit(0)

anchor = '''@app.route("/api/queue/<niche>")
def api_queue(niche):
    mode, items = q_queue(niche)
    return jsonify(success=True, niche=niche, mode=mode, items=items)'''

if anchor not in src:
    print("❌ Could not find /api/queue/<niche> anchor")
    print("   Run: findstr /N /C:\"/api/queue\" app.py")
    sys.exit(1)

new_block = anchor + '''


# ---- Staged queue: delete before drain ----
def _delete_staged_one(pid):
    with conn().cursor() as cur:
        cur.execute("DELETE FROM staged_posts WHERE id=%s", (pid,))
        return cur.rowcount


def _delete_staged_pending(niche, statuses=("pending",)):
    with conn().cursor() as cur:
        cur.execute("""
            DELETE FROM staged_posts
             WHERE niche=%s AND status = ANY(%s)
        """, (niche, list(statuses)))
        return cur.rowcount


@app.route("/api/staged/<niche>", methods=["GET"])
def api_staged_list(niche):
    """List every staged row for a niche (same shape as /api/queue)."""
    mode, items = q_queue(niche)
    return jsonify(success=True, niche=niche, mode=mode, items=items)


@app.route("/api/staged/<niche>/<int:pid>", methods=["DELETE"])
def api_staged_delete_one(niche, pid):
    """Hard-delete one staged row. Only pending rows are safe to delete."""
    try:
        n = _delete_staged_one(pid)
        return jsonify(success=True, deleted=n)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/api/staged/<niche>/clear", methods=["POST"])
def api_staged_clear(niche):
    """Delete every pending staged row for a niche."""
    body = request.get_json(silent=True) or {}
    statuses = body.get("statuses") or ["pending"]
    try:
        n = _delete_staged_pending(niche, statuses=tuple(statuses))
        return jsonify(success=True, deleted=n)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500'''

src = src.replace(anchor, new_block, 1)

try:
    ast.parse(src)
except SyntaxError as e:
    print(f"❌ syntax error: {e}")
    print(f"↩️  Restored: {APP}")
    shutil.copy2(backup, APP)
    sys.exit(1)

open(APP, "w", encoding="utf-8").write(src)
print("✅ Added 4 routes + 2 helpers to app.py")
print()
print("🎯 Verify:")
print('   python -c "import ast; ast.parse(open(\'app.py\',encoding=\'utf-8\').read()); print(\'OK\')"')
print()
print("🎯 Then restart the staging viewer and hit:")
print("   curl http://localhost:5050/api/staged/obiyang09")