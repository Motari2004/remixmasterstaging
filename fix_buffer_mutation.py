"""
Fix the createPost mutation in staging-service/app.py.

Buffer changed createPost to return PostActionPayload (a union) instead
of a plain { post { id } } object. We must use an inline fragment:

    ... on PostActionSuccess { post { id status } }
    ... on MutationError     { message }

This patch rewrites the query string and the response parser.
"""
import os, sys, shutil, datetime, re

APP = r"C:\Users\PC\Desktop\staging-service\app.py"
ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

if not os.path.exists(APP):
    print(f"❌ Not found: {APP}"); sys.exit(1)

with open(APP, "r", encoding="utf-8") as f:
    src = f.read()

shutil.copy2(APP, f"{APP}.bak.{ts}")
print(f"📦 Backup: {APP}.bak.{ts}\n")

# ---- 1. Replace the query block ----
old_query = '''    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        post { id status }
      }
    }
    """'''

new_query = '''    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post { id status }
        }
        ... on MutationError {
          message
        }
      }
    }
    """'''

if old_query not in src:
    print("❌ Could not find the old query block")
    print("   Check that _buffer_queue_post in app.py still has the original query")
    sys.exit(1)

src = src.replace(old_query, new_query, 1)
print("✅ Query updated to use PostActionPayload union")

# ---- 2. Replace the response parser ----
old_parse = '''    data = _buffer_gql(api_key, query, variables)
    post = ((data.get("createPost") or {}).get("post") or {})
    return post.get("id") or ""'''

new_parse = '''    data = _buffer_gql(api_key, query, variables)
    payload = data.get("createPost") or {}
    if payload.get("message"):
        raise RuntimeError(f"Buffer rejected: {payload['message']}")
    post = payload.get("post") or {}
    pid = post.get("id") or ""
    if not pid:
        raise RuntimeError(f"Buffer returned no post id: {payload}")
    return pid'''

if old_parse not in src:
    print("❌ Could not find the old parse block")
    print("   Check that _buffer_queue_post in app.py still has the original parser")
    sys.exit(1)

src = src.replace(old_parse, new_parse, 1)
print("✅ Response parser updated")

with open(APP, "w", encoding="utf-8") as f:
    f.write(src)

print(f"\n✅ Wrote: {APP}")
print(f"📦 Backup: {APP}.bak.{ts}")
print()
print("🎯 Verify:")
print('   python -c "import ast; ast.parse(open(\'app.py\',encoding=\'utf-8\').read()); print(\'syntax OK\')"')
print()
print("🎯 Then:")
print("   git add app.py")
print('   git commit -m "fix buffer createPost mutation for PostActionPayload union"')
print("   git push")