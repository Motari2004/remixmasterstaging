"""
Add the Queue tab to staging-service/templates/index.html.

5 edits:
  1. nav button  🗂️ Queue
  2. <section id="view-queue"> before the LOG section
  3. JS block (loadQueueNiches / openStagedQueue / renderStagedQueue)
  4. nav click handler wires "queue" -> loadQueueNiches()
  5. CSS for the Queue tab

Atomic: backs up, restores on anchor miss or brace imbalance.
Idempotent: skips if id="view-queue" already exists.
"""
import os, sys, shutil, datetime

HERE = r"C:\Users\PC\Desktop\staging-service"
HTML = os.path.join(HERE, "templates", "index.html")
ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

if not os.path.exists(HTML):
    print(f"❌ Not found: {HTML}"); sys.exit(1)

src = open(HTML, encoding="utf-8").read()
backup = f"{HTML}.bak.{ts}"
shutil.copy2(HTML, backup)
print(f"📦 Backup: {backup}")

if 'id="view-queue"' in src:
    print("·  Queue tab already present — nothing to do")
    sys.exit(0)


def restore_and_exit(msg):
    print(f"❌ {msg}")
    shutil.copy2(backup, HTML)
    print(f"↩️  Restored: {HTML}")
    sys.exit(1)


# ---- 1. Nav button ----
old_nav = '    <button data-nav="log" role="tab">📜 Sent Log</button>'
if old_nav not in src:
    restore_and_exit("Could not find nav button anchor")
new_nav = ('    <button data-nav="queue" role="tab">🗂️ Queue</button>\n'
           '    <button data-nav="log" role="tab">📜 Sent Log</button>')
src = src.replace(old_nav, new_nav, 1)
print("✅ nav button")

# ---- 2. Section HTML ----
old_sect = '  <!-- =================== LOG =================== -->'
if old_sect not in src:
    restore_and_exit("Could not find LOG section anchor")
new_sect = '''  <!-- =================== QUEUE =================== -->
  <section id="view-queue" class="view">
    <div class="queue-header">
      <div class="queue-title-row">
        <div class="queue-title" id="queue-title">🗂️ Staged Queue</div>
        <div class="queue-niche-pick">
          <select id="queue-niche" class="accounts-search">
            <option value="">— pick a niche —</option>
          </select>
        </div>
      </div>
    </div>
    <div id="queue-body" class="queue-body">
      <div class="empty">Pick a niche above to see its staged queue.</div>
    </div>
  </section>

  <!-- =================== LOG =================== -->'''
src = src.replace(old_sect, new_sect, 1)
print("✅ section HTML")

# ---- 3. JS before loadDashboard() ----
old_js = 'loadDashboard();'
if old_js not in src:
    restore_and_exit("Could not find loadDashboard() anchor")

js_block = '''// -----------------------------------------------------
// STAGED QUEUE TAB
// -----------------------------------------------------
async function loadQueueNiches() {
  try {
    const r = await fetch("/api/summary");
    const d = await r.json();
    const rows = d.rows || [];
    const sel = $("queue-niche");
    const current = sel.value;
    sel.innerHTML = `<option value="">— pick a niche —</option>` +
      rows.map(n => `<option value="${esc(n.key)}">${esc(n.label || n.key)}</option>`).join("");
    if (current) sel.value = current;
  } catch (e) {
    console.warn("loadQueueNiches:", e);
  }
}

async function openStagedQueue(niche) {
  $("queue-title").textContent = `🗂️ Staged Queue — ${niche}`;
  const body = $("queue-body");
  body.innerHTML = `<div class="empty">Loading…</div>`;
  try {
    const r = await fetch(`/api/staged/${niche}`);
    const d = await r.json();
    if (!d.success) throw new Error(d.error || "failed");
    renderStagedQueue(niche, d.items || [], d.mode);
  } catch (e) {
    body.innerHTML = `<div class="empty err">Error: ${esc(e.message)}</div>`;
  }
}

function renderStagedQueue(niche, items, mode) {
  const body = $("queue-body");
  if (!items.length) {
    body.innerHTML = `<div class="empty">Queue is empty for <strong>${esc(niche)}</strong>.</div>`;
    return;
  }
  const pending = items.filter(i => i.status === "pending").length;
  body.innerHTML = `
    <div class="queue-toolbar">
      <span class="queue-meta">${pending} pending · ${items.length} total · mode=${esc(mode || "direct")}</span>
      <button class="btn" id="queue-clear" data-niche="${esc(niche)}"
              ${pending === 0 ? "disabled" : ""}>Clear pending</button>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>ID</th><th>Title</th><th>Status</th><th>Queued</th><th></th>
        </tr></thead>
        <tbody>
          ${items.map(i => `
            <tr data-row-id="${i.id}">
              <td><code>${i.id}</code></td>
              <td class="title-cell">${esc(i.title || "—")}</td>
              <td><span class="pill ${esc(i.status)}">${esc(i.status)}</span></td>
              <td>${esc(i.queued_at || "")}</td>
              <td>
                ${i.status === "pending"
                  ? `<button class="btn queue-del" data-id="${i.id}" data-niche="${esc(niche)}">✕ Remove</button>`
                  : ""}
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  body.querySelectorAll(".queue-del").forEach(b => {
    b.addEventListener("click", async () => {
      const pid = b.dataset.id;
      if (!confirm(`Remove staged item ${pid}?`)) return;
      try {
        const r = await fetch(`/api/staged/${niche}/${pid}`, { method: "DELETE" });
        const d = await r.json();
        if (!d.success) throw new Error(d.error || "failed");
        document.querySelector(`tr[data-row-id="${pid}"]`)?.remove();
        toast("Removed");
      } catch (e) {
        toast(`Delete failed: ${e.message}`, true);
      }
    });
  });

  const clearBtn = $("queue-clear");
  if (clearBtn) {
    clearBtn.addEventListener("click", async () => {
      if (!confirm(`Delete ALL pending staged items for ${niche}?`)) return;
      try {
        const r = await fetch(`/api/staged/${niche}/clear`, { method: "POST" });
        const d = await r.json();
        if (!d.success) throw new Error(d.error || "failed");
        toast(`Removed ${d.deleted} item(s)`);
        openStagedQueue(niche);
      } catch (e) {
        toast(`Clear failed: ${e.message}`, true);
      }
    });
  }
}

document.addEventListener("change", (e) => {
  if (e.target && e.target.id === "queue-niche") {
    const n = e.target.value;
    if (n) openStagedQueue(n);
    else $("queue-body").innerHTML = `<div class="empty">Pick a niche above.</div>`;
  }
});

loadDashboard();'''

src = src.replace(old_js, js_block, 1)
print("✅ JS block")

# ---- 4. Nav click handler ----
old_h = '    if (t === "log") loadLog();'
if old_h not in src:
    restore_and_exit("Could not find nav handler anchor")
new_h = ('    if (t === "queue")  loadQueueNiches();\n'
         '    if (t === "log") loadLog();')
src = src.replace(old_h, new_h, 1)
print("✅ nav handler")

# ---- 5. CSS ----
old_css = '''    /* =====================================================
       16. RESPONSIVE — TABLET
       ===================================================== */'''
if old_css not in src:
    restore_and_exit("Could not find CSS anchor")

new_css = '''    /* =====================================================
       QUEUE TAB
       ===================================================== */
    .queue-header { margin-bottom: var(--s-4); }
    .queue-title-row {
      display: flex;
      flex-direction: column;
      gap: var(--s-3);
    }
    .queue-title { font-size: 1.05rem; font-weight: 700; }
    .queue-niche-pick select { max-width: 340px; }
    .queue-toolbar {
      display: flex;
      align-items: center;
      gap: var(--s-3);
      margin-bottom: var(--s-3);
      flex-wrap: wrap;
    }
    .queue-meta {
      color: var(--muted);
      font-size: 0.78rem;
      flex: 1 1 auto;
    }
    .pill.pending  { background: rgba(245,158,11,0.14); color: var(--warn-soft);
                     border-color: rgba(245,158,11,0.25); }
    .pill.sending  { background: rgba(0,212,255,0.14);  color: var(--accent2);
                     border-color: rgba(0,212,255,0.25); }
    .pill.sent     { background: rgba(34,197,94,0.14);  color: var(--ok-soft);
                     border-color: rgba(34,197,94,0.25); }
    .pill.failed   { background: rgba(239,68,68,0.14);  color: var(--danger-soft);
                     border-color: rgba(239,68,68,0.25); }
    .pill.cancelled{ background: rgba(139,148,167,0.14); color: var(--muted);
                     border-color: rgba(139,148,167,0.25); }

    /* =====================================================
       16. RESPONSIVE — TABLET
       ===================================================== */'''
src = src.replace(old_css, new_css, 1)
print("✅ CSS block")

# ---- brace check ----
if src.count("{") != src.count("}"):
    restore_and_exit("Brace imbalance after patch")

open(HTML, "w", encoding="utf-8").write(src)
print()
print(f"✅ Wrote: {HTML}")
print(f"📦 Backup: {backup}")
print()
print("🎯 Restart the staging viewer, then open the Queue tab in the browser.")