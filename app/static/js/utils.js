window.__BROKEATM_SETTINGS = window.__BROKEATM_SETTINGS || { default_currency: "CAD" };
window.__BROKEATM_SETTINGS_LOADED = window.__BROKEATM_SETTINGS_LOADED || false;

function setAppSettingsCache(settings) {
  const next = {
    ...window.__BROKEATM_SETTINGS,
    ...(settings || {}),
    default_currency: (settings?.default_currency || window.__BROKEATM_SETTINGS.default_currency || "CAD").toUpperCase(),
  };
  window.__BROKEATM_SETTINGS = next;
  window.__BROKEATM_SETTINGS_LOADED = true;
  window.dispatchEvent(new CustomEvent("app-settings-updated", { detail: next }));
  return next;
}

function getAppCurrency() {
  return window.__BROKEATM_SETTINGS?.default_currency || "CAD";
}

async function loadAppSettings(force = false) {
  if (!force && window.__BROKEATM_SETTINGS_LOADED) {
    return window.__BROKEATM_SETTINGS;
  }
  try {
    const res = await fetch("/api/settings");
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    return setAppSettingsCache(await res.json());
  } catch (_) {
    return setAppSettingsCache({ default_currency: "CAD" });
  }
}

function fmtCurrency(amount, currency = getAppCurrency(), options = {}) {
  const value = Number(amount) || 0;
  const {
    minimumFractionDigits = 2,
    maximumFractionDigits = 2,
    notation,
  } = options;
  try {
    return new Intl.NumberFormat("en-CA", {
      style: "currency",
      currency,
      minimumFractionDigits,
      maximumFractionDigits,
      notation,
    }).format(value);
  } catch (_) {
    return `${currency} ${value.toFixed(maximumFractionDigits)}`;
  }
}

function fmtCurrencyCompact(amount, currency = getAppCurrency()) {
  return fmtCurrency(amount, currency, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
    notation: "compact",
  });
}

function fmtDate(dateStr) {
  if (!dateStr) return "-";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-CA", { year: "numeric", month: "short", day: "numeric" });
}

/** ISO datetime or date string from API */
function fmtDateTime(isoStr) {
  if (!isoStr) return "-";
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return String(isoStr);
  return d.toLocaleString("en-CA", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function typeBadge(type) {
  const map = {
    expense: ["badge-expense", "Expense"],
    income: ["badge-income", "Income"],
    refund: ["badge-refund", "Refund"],
    transfer: ["badge-transfer", "Transfer"],
  };
  const [cls, label] = map[type] || ["badge", type];
  return `<span class="badge ${cls}">${label}</span>`;
}

function showAlert(container, message, type = "error") {
  const el = document.createElement("div");
  el.className = `alert alert-${type}`;
  el.textContent = message;
  container.prepend(el);
  setTimeout(() => el.remove(), 6000);
}

function setActive(navHref) {
  document.querySelectorAll(".nav-links a").forEach((a) => {
    a.classList.toggle("active", a.getAttribute("href") === navHref);
  });
}

function monthLabel(year, month) {
  return new Date(year, month - 1, 1).toLocaleDateString("en-CA", { year: "numeric", month: "short" });
}

function escHtml(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/**
 * Custom confirm dialog. Returns Promise<boolean>.
 * Usage: if (!await confirmDialog({ title, message, confirmLabel })) return;
 */
function confirmDialog({ title = "Confirm", message = "", confirmLabel = "Confirm", confirmClass = "btn-danger", cancelLabel = "Cancel" } = {}) {
  return new Promise(resolve => {
    let overlay = document.getElementById("__confirm-overlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "__confirm-overlay";
      overlay.className = "modal-overlay";
      overlay.style.display = "none";
      overlay.innerHTML = `
        <div class="modal" style="max-width:420px">
          <h2 id="__confirm-title" style="margin-bottom:0.6rem"></h2>
          <p id="__confirm-msg" style="color:var(--text-muted);font-size:0.9rem;margin:0;white-space:pre-wrap"></p>
          <div class="modal-actions">
            <button class="btn btn-secondary btn-sm" id="__confirm-cancel"></button>
            <button class="btn btn-sm" id="__confirm-ok"></button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      overlay.addEventListener("click", e => { if (e.target === overlay) cleanup(false); });
    }
    document.getElementById("__confirm-title").textContent = title;
    document.getElementById("__confirm-msg").textContent = message;
    const okBtn = document.getElementById("__confirm-ok");
    const cancelBtn = document.getElementById("__confirm-cancel");
    okBtn.textContent = confirmLabel;
    okBtn.className = `btn btn-sm ${confirmClass}`;
    cancelBtn.textContent = cancelLabel;
    overlay.style.display = "flex";

    function cleanup(result) {
      overlay.style.display = "none";
      okBtn.onclick = null;
      cancelBtn.onclick = null;
      resolve(result);
    }
    okBtn.onclick = () => cleanup(true);
    cancelBtn.onclick = () => cleanup(false);
  });
}

function debounce(fn, ms = 300) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

// Called once per page load to catch up any due recurring entries.
// Shows a toast at the top of the page if entries were created.
async function processRecurringOnLoad() {
  try {
    const result = await fetch("/api/recurring/process", { method: "POST" }).then(r => r.json());
    if (result.created > 0) {
      const container = document.getElementById("alerts") || document.body;
      showAlert(container, `${result.created} recurring entr${result.created === 1 ? "y" : "ies"} added automatically.`, "success");
    }
  } catch (_) {
    // silently ignore — recurring is best-effort
  }
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else node.setAttribute(k, v);
  }
  for (const child of children) {
    if (typeof child === "string") node.appendChild(document.createTextNode(child));
    else if (child) node.appendChild(child);
  }
  return node;
}
