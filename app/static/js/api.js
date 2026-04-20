async function parseApiError(res) {
  const text = await res.text();
  try {
    const j = JSON.parse(text);
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail)) {
      return j.detail
        .map((x) => (typeof x === "string" ? x : x.msg || JSON.stringify(x)))
        .join(" ");
    }
  } catch (_) {
    /* not JSON */
  }
  return text.trim() || `Request failed (${res.status})`;
}

const API = {
  async getAppSettings() {
    const res = await fetch("/api/settings");
    if (!res.ok) throw new Error(await parseApiError(res));
    return res.json();
  },

  async updateAppSettings(payload) {
    const res = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await parseApiError(res));
    return res.json();
  },

  async parseCSV(file) {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/import/parse", { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async checkDuplicates(rows) {
    const res = await fetch("/api/import/check-duplicates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async commitImport(payload) {
    const res = await fetch("/api/import/commit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getLatestMonth() {
    const res = await fetch("/api/transactions/latest-month");
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getTransactionSummary(params = {}) {
    const qs = new URLSearchParams(
      Object.fromEntries(
        Object.entries(params).filter(([, v]) => v != null && v !== "" && v !== false)
      )
    ).toString();
    const res = await fetch(`/api/transactions/summary${qs ? "?" + qs : ""}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getTransactions(params = {}) {
    const qs = new URLSearchParams(
      Object.fromEntries(
        Object.entries(params).filter(([, v]) => v != null && v !== "" && v !== false)
      )
    ).toString();
    const res = await fetch(`/api/transactions${qs ? "?" + qs : ""}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getDuplicateReport() {
    const res = await fetch("/api/transactions/duplicate-report");
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async pruneExactDuplicates(confirm) {
    const res = await fetch("/api/transactions/prune-exact-duplicates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm }),
    });
    if (!res.ok) throw new Error(await parseApiError(res));
    return res.json();
  },

  async updateTransaction(id, payload) {
    const res = await fetch(`/api/transactions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await parseApiError(res));
    return res.json();
  },

  async createTransaction(payload) {
    const res = await fetch("/api/transactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async deleteTransaction(id) {
    const res = await fetch(`/api/transactions/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(await res.text());
  },

  async bulkDelete(ids) {
    const res = await fetch("/api/transactions/bulk-delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async bulkUpdate(ids, fields) {
    const res = await fetch("/api/transactions/bulk-update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, ...fields }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getCategories() {
    const res = await fetch("/api/categories");
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async createCategory(payload) {
    const res = await fetch("/api/categories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await parseApiError(res);
      if (res.status === 409 || /already exists/i.test(detail)) {
        throw new Error(
          "A category with that name already exists. Choose a different name or merge categories below."
        );
      }
      throw new Error(detail);
    }
    return res.json();
  },

  async updateCategory(id, payload) {
    const res = await fetch(`/api/categories/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await parseApiError(res);
      throw new Error(detail || "Could not update category.");
    }
    return res.json();
  },

  async deleteCategory(id) {
    const res = await fetch(`/api/categories/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(await res.text());
  },

  async getAccounts() {
    const res = await fetch("/api/accounts");
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getAvailableMonths() {
    const res = await fetch("/api/dashboard/available-months");
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getDashboard(params = {}) {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ""))
    ).toString();
    const res = await fetch(`/api/dashboard${qs ? "?" + qs : ""}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getRecurringRules() {
    const res = await fetch("/api/recurring");
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async createRecurringRule(payload) {
    const res = await fetch("/api/recurring", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await parseApiError(res));
    return res.json();
  },

  async updateRecurringRule(id, payload) {
    const res = await fetch(`/api/recurring/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      const err = new Error(body?.detail?.message || body?.detail || "Update failed");
      if (res.status === 409 && body?.detail?.needs_confirmation) {
        err.scheduleImpact = body.detail;
        if (body.detail.overlap_count) err.overlap = body.detail;
      }
      throw err;
    }
    return res.json();
  },

  async deleteRecurringRule(id) {
    const res = await fetch(`/api/recurring/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(await res.text());
  },

  async deleteRecurringRuleFrom(id, from_date) {
    const res = await fetch(`/api/recurring/${id}/delete-from`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from_date }),
    });
    if (!res.ok) throw new Error(await parseApiError(res));
    return res.json();
  },

  async processRecurring() {
    const res = await fetch("/api/recurring/process", { method: "POST" });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getLargeExpenses(params = {}) {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== "" && v !== false && v !== undefined))
    ).toString();
    const res = await fetch(`/api/dashboard/large-expenses${qs ? "?" + qs : ""}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
};
