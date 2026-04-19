(function () {
  const MODAL_ID = "add-tx-modal";

  let _onSuccess = null;
  let _atxCategories = [];

  function injectHTML() {
    if (document.getElementById(MODAL_ID)) return;
    document.body.insertAdjacentHTML("beforeend", `
      <div class="modal-overlay hidden" id="${MODAL_ID}">
        <div class="modal">
          <h2>Add Transaction</h2>
          <div id="atx-alerts"></div>
          <div style="display:grid;gap:0.75rem">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
              <div>
                <label id="atx-date-label">Date <span style="color:var(--danger)">*</span></label>
                <input type="date" id="atx-date" required />
              </div>
              <div>
                <label id="atx-amount-label">Amount <span style="color:var(--danger)">*</span></label>
                <input type="number" id="atx-amount" step="0.01" min="0" required />
              </div>
            </div>
            <div>
              <label>Merchant / Description <span style="color:var(--danger)">*</span></label>
              <input type="text" id="atx-merchant" required />
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
              <div>
                <label>Type</label>
                <select id="atx-type">
                  <option value="expense">Expense</option>
                  <option value="income">Income</option>
                  <option value="refund">Refund</option>
                  <option value="transfer">Transfer</option>
                </select>
              </div>
              <div>
                <label>Category</label>
                <div style="display:flex;gap:0.5rem;align-items:stretch">
                  <input type="hidden" id="atx-category" value="" />
                  <button type="button" class="category-picker-trigger" id="atx-category-trigger" style="flex:1;min-height:38px;font-size:0.91rem;padding:0.3rem 0.85rem">
                    <span class="category-picker-trigger-label" id="atx-category-trigger-label">No category</span>
                    <span class="category-picker-trigger-caret" aria-hidden="true">▾</span>
                  </button>
                  <button type="button" class="btn btn-secondary btn-field-action" id="atx-new-category">+ Category</button>
                </div>
              </div>
            </div>
            <div>
              <label>Account</label>
              <select id="atx-account"></select>
            </div>
            <div>
              <label>Notes</label>
              <textarea id="atx-notes" rows="2" placeholder="Optional note\u2026"></textarea>
            </div>

            <!-- Recurring toggle row -->
            <div style="display:flex;align-items:center;gap:0.6rem;padding-top:0.25rem">
              <label style="position:relative;display:inline-block;width:40px;height:22px;flex-shrink:0">
                <input type="checkbox" id="atx-recur-toggle" style="opacity:0;width:0;height:0;position:absolute" />
                <span id="atx-recur-slider"
                  style="position:absolute;inset:0;border-radius:22px;background:var(--border);cursor:pointer;transition:background 0.2s">
                  <span id="atx-recur-knob"
                    style="position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:transform 0.2s;pointer-events:none"></span>
                </span>
              </label>
              <span class="text-meta text-muted" style="font-weight:600" id="atx-recur-label">Recurring</span>
            </div>

            <!-- Recurring fields (hidden by default) -->
            <div id="atx-recurring-section" style="display:none;border-top:1px solid var(--border);padding-top:0.75rem">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
                <div>
                  <label>Repeat every</label>
                  <select id="atx-recur-freq">
                    <option value="monthly">Monthly</option>
                    <option value="weekly">Weekly</option>
                    <option value="biweekly">Bi-weekly</option>
                    <option value="yearly">Yearly</option>
                  </select>
                </div>
                <div>
                  <label>Ends</label>
                  <select id="atx-recur-ends">
                    <option value="forever">Never (forever)</option>
                    <option value="on">On a date</option>
                  </select>
                </div>
              </div>
              <div id="atx-recur-end-row" style="display:none;margin-top:0.75rem">
                <label>End date</label>
                <input type="date" id="atx-recur-end" style="color-scheme:dark" />
              </div>
              <div id="atx-recur-preview" class="text-meta text-muted" style="margin-top:0.6rem;min-height:1.2em"></div>
            </div>
          </div>
          <div class="modal-actions">
            <button class="btn btn-secondary" id="atx-cancel">Cancel</button>
            <button class="btn btn-primary" id="atx-save">Add</button>
          </div>
        </div>
      </div>
    `);
    bindEvents();
  }

  function bindEvents() {
    document.getElementById("atx-cancel").addEventListener("click", closeModal);
    document.getElementById(MODAL_ID).addEventListener("click", (e) => {
      if (e.target === document.getElementById(MODAL_ID)) closeModal();
    });

    const toggle = document.getElementById("atx-recur-toggle");
    toggle.addEventListener("change", () => {
      const on = toggle.checked;
      document.getElementById("atx-recur-slider").style.background = on ? "var(--accent)" : "var(--border)";
      document.getElementById("atx-recur-knob").style.transform = on ? "translateX(18px)" : "translateX(0)";
      document.getElementById("atx-recur-label").style.color = on ? "var(--text)" : "var(--text-muted)";
      document.getElementById("atx-recurring-section").style.display = on ? "" : "none";
      document.getElementById("atx-date-label").innerHTML = on
        ? 'Start date <span style="color:var(--danger)">*</span>'
        : 'Date <span style="color:var(--danger)">*</span>';
      updatePreview();
    });

    document.getElementById("atx-recur-ends").addEventListener("change", () => {
      const onDate = document.getElementById("atx-recur-ends").value === "on";
      document.getElementById("atx-recur-end-row").style.display = onDate ? "" : "none";
      updatePreview();
    });

    ["atx-recur-end", "atx-recur-freq", "atx-date"].forEach(id =>
      document.getElementById(id).addEventListener("change", updatePreview)
    );

    document.getElementById("atx-save").addEventListener("click", saveEntry);
    document.getElementById("atx-category-trigger").addEventListener("click", async (event) => {
      const currentVal = document.getElementById("atx-category").value;
      const picked = await openCategoryPickerModal({
        title: "Set category",
        searchPlaceholder: "Search categories...",
        selectedValue: currentVal ? +currentVal : null,
        actionLabel: "Select",
        items: _atxCategories.map(c => ({
          id: c.id,
          value: c.id,
          name: c.name,
          color: c.color || "",
        })),
        emptyMessage: "No categories available yet.",
        noResultsMessage: (q) => `No categories match "${q}".`,
        mode: "popover",
        anchorEl: event.currentTarget,
      });
      if (!picked) return;
      document.getElementById("atx-category").value = picked.value === null ? "" : String(picked.id);
      document.getElementById("atx-category-trigger-label").textContent = picked.value === null ? "No category" : picked.name;
    });
    document.getElementById("atx-new-category").addEventListener("click", async () => {
      const created = await openCategoryCreateModal({
        title: "Create Category",
        onCategoriesUpdated: async (cats) => {
          await refreshCategoryOptions(cats);
        },
      });
      if (created) {
        await refreshCategoryOptions(null, created.id);
      }
    });
  }

  function updateCurrencyLabel() {
    const currency = getAppCurrency();
    document.getElementById("atx-amount-label").innerHTML =
      `Amount (${escHtml(currency)}) <span style="color:var(--danger)">*</span>`;
  }

  function updatePreview() {
    const el = document.getElementById("atx-recur-preview");
    if (!document.getElementById("atx-recur-toggle").checked) { el.textContent = ""; return; }
    const startVal = document.getElementById("atx-date").value;
    const freq = document.getElementById("atx-recur-freq").value;
    const endsMode = document.getElementById("atx-recur-ends").value;
    const freqLabel = { monthly: "monthly", weekly: "weekly", biweekly: "bi-weekly", yearly: "yearly" }[freq];

    if (endsMode === "forever") {
      el.textContent = startVal
        ? `Repeats ${freqLabel} from ${startVal}, forever`
        : `Repeats ${freqLabel}, forever`;
      return;
    }

    const endVal = document.getElementById("atx-recur-end").value;
    if (!startVal || !endVal) { el.textContent = ""; return; }

    const start = new Date(startVal + "T00:00:00");
    const end = new Date(endVal + "T00:00:00");
    if (start > end) { el.textContent = "End date must be after start date."; return; }

    el.textContent = `Repeats ${freqLabel} from ${startVal} to ${endVal}`;
  }

  function closeModal() {
    document.getElementById(MODAL_ID).classList.add("hidden");
  }

  async function refreshCategoryOptions(providedCategories = null, selectedId = null) {
    _atxCategories = providedCategories || await API.getCategories().catch(() => []);
    const catId = selectedId ? String(selectedId) : "";
    document.getElementById("atx-category").value = catId;
    const selectedCat = selectedId ? _atxCategories.find(c => c.id === selectedId) : null;
    document.getElementById("atx-category-trigger-label").textContent =
      selectedCat ? selectedCat.name : "No category";
  }

  async function saveEntry() {
    const dateVal = document.getElementById("atx-date").value;
    const merchantVal = document.getElementById("atx-merchant").value.trim();
    const amountVal = parseFloat(document.getElementById("atx-amount").value);
    const alertBox = document.getElementById("atx-alerts");
    const isRecurring = document.getElementById("atx-recur-toggle").checked;

    if (!dateVal || !merchantVal || isNaN(amountVal) || amountVal < 0) {
      showAlert(alertBox, "Date, merchant, and a valid amount are required.", "error");
      return;
    }

    const base = {
      merchant_name: merchantVal,
      amount: amountVal,
      transaction_type: document.getElementById("atx-type").value,
      category_id: document.getElementById("atx-category").value
        ? +document.getElementById("atx-category").value : null,
      account_id: document.getElementById("atx-account").value
        ? +document.getElementById("atx-account").value : null,
      notes: document.getElementById("atx-notes").value.trim() || null,
      currency: getAppCurrency(),
    };

    try {
      if (isRecurring) {
        const endsMode = document.getElementById("atx-recur-ends").value;
        const endVal = endsMode === "on" ? document.getElementById("atx-recur-end").value : null;

        if (endsMode === "on" && !endVal) {
          showAlert(alertBox, "Set an end date, or choose Never.", "error");
          return;
        }
        if (endVal && endVal < dateVal) {
          showAlert(alertBox, "End date must be after start date.", "error");
          return;
        }

        await API.createRecurringRule({
          ...base,
          frequency: document.getElementById("atx-recur-freq").value,
          start_date: dateVal,
          end_date: endVal || null,
        });

        const result = await API.processRecurring();
        closeModal();
        if (_onSuccess) _onSuccess(result.created, true);
      } else {
        await API.createTransaction({ ...base, transaction_date: dateVal });
        closeModal();
        if (_onSuccess) _onSuccess(1, false);
      }
    } catch (e) {
      showAlert(alertBox, e.message, "error");
    }
  }

  async function open(opts = {}) {
    injectHTML();
    _onSuccess = opts.onSuccess || null;
    await loadAppSettings();
    updateCurrencyLabel();

    const [cats, accs] = await Promise.all([
      API.getCategories().catch(() => []),
      API.getAccounts().catch(() => []),
    ]);

    await refreshCategoryOptions(cats);

    document.getElementById("atx-account").innerHTML =
      '<option value="">No account</option>' +
      accs.map(a => `<option value="${a.id}">${escHtml(a.name)}</option>`).join("");

    document.getElementById("atx-date").value = new Date().toISOString().slice(0, 10);
    document.getElementById("atx-merchant").value = "";
    document.getElementById("atx-amount").value = "";
    document.getElementById("atx-type").value = "expense";
    document.getElementById("atx-category").value = "";
    document.getElementById("atx-category-trigger-label").textContent = "No category";
    document.getElementById("atx-notes").value = "";

    const toggle = document.getElementById("atx-recur-toggle");
    const forceRecurring = !!opts.recurringDefault;
    toggle.checked = forceRecurring;
    document.getElementById("atx-recur-slider").style.background = forceRecurring ? "var(--accent)" : "var(--border)";
    document.getElementById("atx-recur-knob").style.transform = forceRecurring ? "translateX(18px)" : "translateX(0)";
    document.getElementById("atx-recur-label").style.color = forceRecurring ? "var(--text)" : "var(--text-muted)";
    document.getElementById("atx-recurring-section").style.display = forceRecurring ? "" : "none";
    // hide the toggle row when recurring is forced so user can't uncheck it
    document.getElementById("atx-recur-toggle").closest("div[style]").style.display = forceRecurring ? "none" : "";
    document.getElementById("atx-recur-ends").value = "forever";
    document.getElementById("atx-recur-end-row").style.display = "none";
    document.getElementById("atx-recur-end").value = "";
    document.getElementById("atx-recur-freq").value = "monthly";
    document.getElementById("atx-recur-preview").textContent = "";
    document.getElementById("atx-date-label").innerHTML = forceRecurring
      ? 'Start date <span style="color:var(--danger)">*</span>'
      : 'Date <span style="color:var(--danger)">*</span>';

    document.getElementById(MODAL_ID).classList.remove("hidden");
  }

  window.openAddTxModal = open;
})();
