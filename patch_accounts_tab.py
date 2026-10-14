"""
Add the Accounts tab to templates/index.html.

Applies 5 edits in one pass:
  1. Add nav button
  2. Add <section id="view-accounts">
  3. Add JS for loadAccounts / renderAccounts / search / view toggle
  4. Wire nav click to loadAccounts
  5. Add CSS for the Accounts tab
"""
import os, sys, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "templates", "index.html")
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

if not os.path.exists(HTML):
    print(f"❌ Not found: {HTML}"); sys.exit(1)

with open(HTML, "r", encoding="utf-8") as f:
    src = f.read()

shutil.copy2(HTML, f"{HTML}.bak.{ts}")
print(f"📦 Backup: {HTML}.bak.{ts}\n")

if 'id="view-accounts"' in src:
    print("ℹ️  Accounts tab already exists — nothing to do.")
    sys.exit(0)

applied = []

# ---------------------------------------------------------------
# 1. Add nav button
# ---------------------------------------------------------------
old_nav = '    <button data-nav="log" role="tab">📜 Sent Log</button>'
new_nav = ('    <button data-nav="accounts" role="tab">📇 Accounts</button>\n'
           '    <button data-nav="log" role="tab">📜 Sent Log</button>')

if old_nav in src:
    src = src.replace(old_nav, new_nav, 1)
    applied.append("nav button")
else:
    print("❌ Could not find nav button"); sys.exit(1)

# ---------------------------------------------------------------
# 2. Add section HTML (before the LOG section)
# ---------------------------------------------------------------
old_sect = '  <!-- =================== LOG =================== -->'
new_sect = '''  <!-- =================== ACCOUNTS =================== -->
  <section id="view-accounts" class="view">
    <div class="accounts-header">
      <div class="accounts-title">📇 Accounts</div>
      <div class="accounts-actions">
        <span class="accounts-count" id="accounts-count">—</span>
        <div class="view-toggle">
          <button class="view-btn active" data-account-view="workspace">Workspace</button>
          <button class="view-btn" data-account-view="flat">Flat</button>
        </div>
      </div>
    </div>

    <div class="accounts-controls">
      <input type="search" id="accounts-search" class="accounts-search"
             placeholder="Search niche, email, channel id…">
      <div class="accounts-filters" id="accounts-filters"></div>
    </div>

    <div id="accounts-body"></div>
  </section>

  <!-- =================== LOG =================== -->'''

if old_sect in src:
    src = src.replace(old_sect, new_sect, 1)
    applied.append("section HTML")
else:
    print("❌ Could not find LOG section anchor"); sys.exit(1)

# ---------------------------------------------------------------
# 3. Add JS before "// Start"
# ---------------------------------------------------------------
old_js = '''// -----------------------------------------------------
// Start
// -----------------------------------------------------
loadDashboard();'''

new_js = '''// -----------------------------------------------------
// ACCOUNTS TAB
// -----------------------------------------------------
let ACCOUNTS_DATA = null;
let ACCOUNTS_VIEW = "workspace";
let ACCOUNTS_FILTER = "all";
let ACCOUNTS_QUERY = "";

async function loadAccounts() {
  if (!$("accounts-body").innerHTML.trim()) {
    $("accounts-body").innerHTML = `<div class="empty">Loading accounts…</div>`;
  }
  try {
    const r = await fetch("/api/accounts");
    const d = await r.json();
    if (!d.success) throw new Error(d.error || "failed");
    ACCOUNTS_DATA = d.rows || [];
    renderAccounts();
  } catch (e) {
    $("accounts-body").innerHTML =
      `<div class="empty err">Error: ${esc(e.message)}</div>`;
  }
}

function accountMatchesFilter(row, filter) {
  if (filter === "all") return true;
  if (filter === "buffer" || filter === "zernio") return row.publisher === filter;
  if (filter === "missing") return !row.email;
  return row.platform === filter;
}

function accountMatchesQuery(row, q) {
  if (!q) return true;
  const needle = q.toLowerCase();
  return (
    (row.label || "").toLowerCase().includes(needle) ||
    (row.key || "").toLowerCase().includes(needle) ||
    (row.email || "").toLowerCase().includes(needle) ||
    (row.channel_id || "").toLowerCase().includes(needle) ||
    (row.account_id || "").toLowerCase().includes(needle) ||
    (row.profile_id || "").toLowerCase().includes(needle)
  );
}

function renderAccounts() {
  if (!ACCOUNTS_DATA) return;

  const filtered = ACCOUNTS_DATA.filter(r =>
    accountMatchesFilter(r, ACCOUNTS_FILTER) &&
    accountMatchesQuery(r, ACCOUNTS_QUERY)
  );

  const total = ACCOUNTS_DATA.length;
  const withEmail = ACCOUNTS_DATA.filter(r => r.email).length;
  const workspaces = new Set(ACCOUNTS_DATA.map(r => r.email || "__none__")).size;
  $("accounts-count").innerHTML =
    `${filtered.length}/${total} niches · ${withEmail} with email · ${workspaces} workspace(s)`;

  const platforms = Array.from(new Set(ACCOUNTS_DATA.map(r => r.platform).filter(Boolean)));
  const filterDefs = [
    { key: "all", label: "All" },
    { key: "buffer", label: "Buffer" },
    { key: "zernio", label: "Zernio" },
    ...platforms.map(p => ({ key: p, label: p })),
    { key: "missing", label: "Missing email" },
  ];
  $("accounts-filters").innerHTML = filterDefs.map(f =>
    `<button class="chip ${f.key === ACCOUNTS_FILTER ? 'active' : ''}"
             data-account-filter="${f.key}">${esc(f.label)}</button>`
  ).join("");

  $("accounts-filters").querySelectorAll("[data-account-filter]").forEach(b => {
    b.addEventListener("click", () => {
      ACCOUNTS_FILTER = b.dataset.accountFilter;
      renderAccounts();
    });
  });

  if (!filtered.length) {
    $("accounts-body").innerHTML = `<div class="empty">No accounts match.</div>`;
    return;
  }

  if (ACCOUNTS_VIEW === "flat") {
    $("accounts-body").innerHTML = renderAccountsFlat(filtered);
  } else {
    $("accounts-body").innerHTML = renderAccountsWorkspaces(filtered);
  }

  $("accounts-body").querySelectorAll("[data-copy-email]").forEach(b => {
    b.addEventListener("click", () => {
      const email = b.dataset.copyEmail;
      navigator.clipboard.writeText(email).then(() => {
        b.textContent = "✓";
        setTimeout(() => b.textContent = "📋", 1200);
      }).catch(() => toast("Copy failed", true));
    });
  });
}

function renderAccountsFlat(rows) {
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Niche</th><th>Publisher</th><th>Platform</th>
            <th>Email</th><th>Channel / Profile ID</th><th></th>
          </tr>
        </thead>
        <tbody>
          ${rows.map(r => `
            <tr>
              <td><strong>${esc(r.label)}</strong></td>
              <td>${esc(r.publisher)}</td>
              <td>${platformPill(r.platform)}</td>
              <td>
                ${r.email
                  ? `<span class="email-cell">${esc(r.email)}</span>`
                  : `<span class="email-missing">missing</span>`}
              </td>
              <td><code class="id-cell">${esc(r.channel_id || r.profile_id || "—")}</code></td>
              <td>
                ${r.email
                  ? `<button class="copy-btn" data-copy-email="${esc(r.email)}" title="Copy email">📋</button>`
                  : ""}
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderAccountsWorkspaces(rows) {
  const groups = {};
  rows.forEach(r => {
    const k = r.email || "__none__";
    if (!groups[k]) groups[k] = { email: r.email, niches: [] };
    groups[k].niches.push(r);
  });

  const sorted = Object.values(groups).sort((a, b) => {
    if (!a.email && b.email) return 1;
    if (a.email && !b.email) return -1;
    return (a.email || "").localeCompare(b.email || "");
  });

  return sorted.map(g => `
    <div class="workspace">
      <div class="workspace-head">
        <div class="workspace-email">
          ${g.email
            ? `<span class="em">${esc(g.email)}</span>
               <button class="copy-btn" data-copy-email="${esc(g.email)}" title="Copy email">📋</button>`
            : `<span class="em missing">email not set</span>`}
        </div>
        <div class="workspace-count">${g.niches.length} niche${g.niches.length === 1 ? "" : "s"}</div>
      </div>
      <div class="workspace-body">
        ${g.niches.map(r => `
          <div class="workspace-row">
            <div class="wr-name">
              <strong>${esc(r.label)}</strong>
              <span class="wr-key">${esc(r.key)}</span>
            </div>
            <div class="wr-platform">${platformPill(r.platform)}</div>
            <div class="wr-publisher">${esc(r.publisher)}</div>
            <div class="wr-id"><code>${esc(r.channel_id || r.profile_id || r.account_id || "—")}</code></div>
          </div>
        `).join("")}
      </div>
    </div>
  `).join("");
}

document.addEventListener("input", (e) => {
  if (e.target && e.target.id === "accounts-search") {
    ACCOUNTS_QUERY = e.target.value;
    renderAccounts();
  }
});

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-account-view]");
  if (!btn) return;
  ACCOUNTS_VIEW = btn.dataset.accountView;
  document.querySelectorAll("[data-account-view]").forEach(b =>
    b.classList.toggle("active", b === btn));
  renderAccounts();
});

// -----------------------------------------------------
// Start
// -----------------------------------------------------
loadDashboard();'''

if old_js in src:
    src = src.replace(old_js, new_js, 1)
    applied.append("JS block")
else:
    print("❌ Could not find Start block anchor"); sys.exit(1)

# ---------------------------------------------------------------
# 4. Wire nav click to loadAccounts
# ---------------------------------------------------------------
old_nav_handler = '    if (t === "log") loadLog();'
new_nav_handler = ('    if (t === "accounts") loadAccounts();\n'
                   '    if (t === "log") loadLog();')

if old_nav_handler in src:
    src = src.replace(old_nav_handler, new_nav_handler, 1)
    applied.append("nav handler")
else:
    print("❌ Could not find nav handler"); sys.exit(1)

# ---------------------------------------------------------------
# 5. Add CSS (before the RESPONSIVE TABLET block)
# ---------------------------------------------------------------
old_css = '''    /* =====================================================
       16. RESPONSIVE — TABLET
       ===================================================== */'''

new_css = '''    /* =====================================================
       ACCOUNTS TAB
       ===================================================== */
    .accounts-header {
      display: flex;
      flex-direction: column;
      gap: var(--s-3);
      margin-bottom: var(--s-4);
    }
    .accounts-title { font-size: 1.05rem; font-weight: 700; }
    .accounts-actions {
      display: flex;
      align-items: center;
      gap: var(--s-3);
      flex-wrap: wrap;
    }
    .accounts-count {
      color: var(--muted);
      font-size: 0.78rem;
      flex: 1 1 auto;
    }
    .view-toggle {
      display: inline-flex;
      background: var(--panel2);
      border: 1px solid var(--border);
      border-radius: var(--r-md);
      padding: 2px;
      gap: 2px;
    }
    .view-btn {
      appearance: none;
      background: transparent;
      border: 0;
      color: var(--muted);
      font-family: inherit;
      font-size: 0.78rem;
      font-weight: 600;
      padding: 6px 12px;
      border-radius: var(--r-sm);
      cursor: pointer;
      min-height: 32px;
    }
    .view-btn:hover { color: var(--text); }
    .view-btn.active {
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      color: #fff;
    }

    .accounts-controls {
      display: flex;
      flex-direction: column;
      gap: var(--s-3);
      margin-bottom: var(--s-4);
    }
    .accounts-search {
      width: 100%;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--r-md);
      padding: 10px 14px;
      font-size: 0.85rem;
      color: var(--text);
      font-family: inherit;
    }
    .accounts-search::placeholder { color: var(--muted-2); }
    .accounts-search:focus {
      outline: none;
      border-color: var(--accent);
    }

    .accounts-filters {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .chip {
      appearance: none;
      background: var(--panel);
      border: 1px solid var(--border);
      color: var(--muted);
      font-family: inherit;
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 6px 12px;
      border-radius: 999px;
      cursor: pointer;
      transition: all var(--dur) var(--ease);
    }
    .chip:hover { color: var(--text); border-color: var(--accent); }
    .chip.active {
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      border-color: transparent;
      color: #fff;
    }

    .workspace {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--r-lg);
      margin-bottom: var(--s-3);
      overflow: hidden;
    }
    .workspace-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: var(--s-3);
      padding: 12px 16px;
      background: var(--panel2);
      border-bottom: 1px solid var(--border);
    }
    .workspace-email {
      display: flex;
      align-items: center;
      gap: var(--s-2);
      min-width: 0;
    }
    .workspace-email .em {
      font-weight: 600;
      font-size: 0.88rem;
      word-break: break-all;
    }
    .workspace-email .em.missing {
      color: var(--warn-soft);
      font-style: italic;
    }
    .workspace-count {
      color: var(--muted);
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.7px;
      flex-shrink: 0;
    }
    .workspace-body { padding: 4px 0; }
    .workspace-row {
      display: grid;
      grid-template-columns: minmax(0, 2fr) auto auto minmax(0, 1.5fr);
      gap: var(--s-3);
      padding: 10px 16px;
      align-items: center;
      border-bottom: 1px solid var(--border);
      font-size: 0.85rem;
    }
    .workspace-row:last-child { border-bottom: 0; }
    .wr-name { min-width: 0; }
    .wr-name strong { display: block; word-break: break-word; }
    .wr-key {
      display: block;
      color: var(--muted-2);
      font-size: 0.72rem;
      font-family: monospace;
      margin-top: 1px;
    }
    .wr-publisher {
      color: var(--muted);
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .wr-id code, .id-cell {
      font-family: monospace;
      font-size: 0.72rem;
      color: var(--muted);
      background: var(--panel2);
      padding: 2px 6px;
      border-radius: var(--r-sm);
      border: 1px solid var(--border);
    }
    .email-cell {
      font-family: monospace;
      font-size: 0.78rem;
    }
    .email-missing {
      color: var(--warn-soft);
      font-style: italic;
      font-size: 0.78rem;
    }
    .copy-btn {
      appearance: none;
      background: var(--panel2);
      border: 1px solid var(--border);
      border-radius: var(--r-sm);
      color: var(--text);
      padding: 4px 8px;
      font-size: 0.78rem;
      cursor: pointer;
      transition: all var(--dur) var(--ease);
    }
    .copy-btn:hover { border-color: var(--accent); }
    .copy-btn:active { transform: scale(0.95); }

    @media (max-width: 639px) {
      .workspace-row {
        grid-template-columns: 1fr auto;
        row-gap: var(--s-2);
      }
      .wr-platform, .wr-publisher { display: none; }
      .wr-id { grid-column: 1 / -1; }
    }

    /* =====================================================
       16. RESPONSIVE — TABLET
       ===================================================== */'''

if old_css in src:
    src = src.replace(old_css, new_css, 1)
    applied.append("CSS block")
else:
    print("❌ Could not find RESPONSIVE TABLET CSS anchor"); sys.exit(1)

# ---------------------------------------------------------------
# Write
# ---------------------------------------------------------------
with open(HTML, "w", encoding="utf-8") as f:
    f.write(src)

print("✅ Applied:")
for a in applied:
    print(f"   · {a}")
print(f"\n✅ Wrote: {HTML}")
print(f"📦 Backup: {HTML}.bak.{ts}")
print()
print("🎯 Next:")
print("   git add templates/index.html app.py settings.json")
print('   git commit -m "add Accounts tab"')
print("   git push origin main")