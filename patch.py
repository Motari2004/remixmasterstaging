"""
Minimal staged-removal UI:
  - Adds a "Clear staged" button per niche row in the Buffer dashboard table
  - Adds a "Clear staged" button per niche card (mobile)
  - Calls POST /api/staged/<niche>/clear (already in app.py)
  - No new tabs, no per-row delete — one button per niche
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

if "clear-staged" in src:
    print("·  Clear-staged button already present — nothing to do")
    sys.exit(0)


def restore_and_exit(msg):
    print(f"❌ {msg}")
    shutil.copy2(backup, HTML)
    print(f"↩️  Restored: {HTML}")
    sys.exit(1)


# ---- 1. Dashboard table: add a column + button ----
old_thead = '''              <th>Pending</th><th>Sent today</th><th>Last drain</th>
            </tr>'''
new_thead = '''              <th>Pending</th><th>Sent today</th><th>Last drain</th><th></th>
            </tr>'''
if old_thead not in src:
    restore_and_exit("Could not find dashboard table header")
src = src.replace(old_thead, new_thead, 1)

old_row = '''                <td>${r.pending}</td>
                <td>${r.sent_today}</td>
                <td>${esc(fmtDate(r.last_drain))}</td>
              </tr>'''
new_row = '''                <td>${r.pending}</td>
                <td>${r.sent_today}</td>
                <td>${esc(fmtDate(r.last_drain))}</td>
                <td>
                  <button class="btn clear-staged" data-niche="${esc(r.key)}"
                          ${r.pending === 0 ? "disabled" : ""}>
                    🗑 Clear staged
                  </button>
                </td>
              </tr>'''
if old_row not in src:
    restore_and_exit("Could not find dashboard table row")
src = src.replace(old_row, new_row, 1)


# ---- 2. Dashboard cards (mobile): add a Clear staged button ----
old_card_actions = '''            <div class="actions">
              <button class="btn" data-zernio-posts="${esc(r.niche)}">📋 View posts</button>
            </div>'''
# Not present on the buffer card; add a new actions block to the buffer card
old_card = '''              <div class="field">
                <span class="k">Last drain</span>
                <span class="v">${esc(fmtDate(r.last_drain))}</span>
              </div>
            </div>
          </div>
        `).join("")}
      </div>
    `;'''
new_card = '''              <div class="field">
                <span class="k">Last drain</span>
                <span class="v">${esc(fmtDate(r.last_drain))}</span>
              </div>
            </div>
            <div class="actions">
              <button class="btn clear-staged" data-niche="${esc(r.key)}"
                      ${r.pending === 0 ? "disabled" : ""}>
                🗑 Clear staged
              </button>
            </div>
          </div>
        `).join("")}
      </div>
    `;'''
if old_card not in src:
    restore_and_exit("Could not find dashboard card block")
src = src.replace(old_card, new_card, 1)


# ---- 3. JS: wire the buttons after dashboard renders ----
old_js = '''    $("dashboard-body").innerHTML = cardsHtml + tableHtml;
  } catch (e) {
    toast("Dashboard error: " + e.message, true);
  }
}'''
new_js = '''    $("dashboard-body").innerHTML = cardsHtml + tableHtml;

    $("dashboard-body").querySelectorAll(".clear-staged").forEach(b => {
      b.addEventListener("click", async () => {
        const niche = b.dataset.niche;
        if (!confirm(`Delete ALL pending staged items for ${niche}?`)) return;
        b.disabled = true;
        b.textContent = "Clearing…";
        try {
          const r = await fetch(`/api/staged/${niche}/clear`, { method: "POST" });
          const d = await r.json();
          if (!d.success) throw new Error(d.error || "failed");
          toast(`Removed ${d.deleted} item(s) from ${niche}`);
          loadDashboard();
        } catch (e) {
          toast(`Clear failed: ${e.message}`, true);
          b.disabled = false;
          b.textContent = "🗑 Clear staged";
        }
      });
    });
  } catch (e) {
    toast("Dashboard error: " + e.message, true);
  }
}'''
if old_js not in src:
    restore_and_exit("Could not find dashboard render block")
src = src.replace(old_js, new_js, 1)


# ---- 4. Brace sanity ----
if src.count("{") != src.count("}"):
    restore_and_exit("Brace imbalance after patch")

open(HTML, "w", encoding="utf-8").write(src)
print("✅ Added Clear-staged button to dashboard table + cards")
print()
print("🎯 Restart the viewer, open the Buffer tab, click 🗑 Clear staged on obiyang09")