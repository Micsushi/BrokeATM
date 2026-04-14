function fmtCurrency(amount, currency = "CAD") {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(amount);
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
