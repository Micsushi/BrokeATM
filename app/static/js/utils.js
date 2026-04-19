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
          <p id="__confirm-msg" class="modal-copy" style="margin:0;white-space:pre-wrap"></p>
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

const CategoryBus = (() => {
  const ch = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("brokeatm_categories") : null;
  const listeners = [];
  if (ch) ch.onmessage = () => listeners.forEach(fn => fn());
  return {
    emit() { ch?.postMessage("changed"); },
    onChanged(fn) { listeners.push(fn); },
  };
})();

function debounce(fn, ms = 300) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

async function processRecurringOnLoad() {
  try {
    const result = await fetch("/api/recurring/process", { method: "POST" }).then(r => r.json());
    if (result.created > 0) {
      const container = document.getElementById("alerts") || document.body;
      showAlert(container, `${result.created} recurring entr${result.created === 1 ? "y" : "ies"} added automatically.`, "success");
    }
  } catch (_) {
    // Ignore recurring catch-up errors.
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

const _IMPORT_JOBS_STORAGE_KEY = "brokeatm-import-pending-jobs";

function _showImportReadyToast(count) {
  let toast = document.getElementById("__import-bg-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "__import-bg-toast";
    toast.className = "app-toast";
    toast.style.cssText = "pointer-events:auto;max-width:320px;line-height:1.4";
    document.body.appendChild(toast);
  }
  toast.innerHTML = `${count} file${count !== 1 ? "s" : ""} parsed and ready. <a href="/import" style="color:#fff;text-decoration:underline">Review \u2192</a>`;
  toast.classList.add("show");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove("show"), 9000);
}

async function pollPendingImportJobs() {
  const raw = localStorage.getItem(_IMPORT_JOBS_STORAGE_KEY);
  if (!raw) return;
  let pending;
  try { pending = JSON.parse(raw); } catch (_) { localStorage.removeItem(_IMPORT_JOBS_STORAGE_KEY); return; }
  if (!Array.isArray(pending) || !pending.length) { localStorage.removeItem(_IMPORT_JOBS_STORAGE_KEY); return; }

  const onImportPage = window.location.pathname === "/import" || window.location.pathname.startsWith("/import?");
  let remaining = [...pending];
  let doneCount = 0;

  const interval = setInterval(async () => {
    if (!remaining.length) { clearInterval(interval); return; }
    const stillPending = [];
    await Promise.all(remaining.map(async (job) => {
      try {
        const res = await fetch(`/api/import/job/${job.job_id}`);
        if (!res.ok) {
          // 404 = job expired (server restart); drop it. Other errors = transient, keep retrying.
          if (res.status !== 404) stillPending.push(job);
          return;
        }
        const data = await res.json();
        if (data.status === "pending") { stillPending.push(job); return; }
        if (data.status === "done") doneCount++;
      } catch (_) {
        stillPending.push(job);
      }
    }));
    remaining = stillPending;
    if (remaining.length) {
      localStorage.setItem(_IMPORT_JOBS_STORAGE_KEY, JSON.stringify(remaining));
    } else {
      localStorage.removeItem(_IMPORT_JOBS_STORAGE_KEY);
      clearInterval(interval);
      if (!onImportPage && doneCount > 0) _showImportReadyToast(doneCount);
    }
  }, onImportPage ? 2000 : 5000);
}

document.addEventListener("DOMContentLoaded", () => { void pollPendingImportJobs(); });
