(function () {
  const MODAL_ID = "keyword-conflict-modal";
  const STYLE_ID = "keyword-conflict-modal-styles";

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${MODAL_ID} .modal {
        width: min(96vw, 680px);
        max-width: 680px;
        max-height: min(92vh, 920px);
        display: grid;
        grid-template-rows: auto auto minmax(0, 1fr) auto;
        gap: 1rem;
        padding: 1.35rem 1.45rem;
        overflow: hidden;
      }
      #${MODAL_ID} .modal h2 {
        margin-bottom: 0;
      }
      #${MODAL_ID} .kcm-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;
      }
      #${MODAL_ID} .kcm-nav {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        margin-left: auto;
      }
      #${MODAL_ID} .kcm-nav:empty {
        display: none;
      }
      #${MODAL_ID} .kcm-nav-btn {
        min-width: 36px;
        min-height: 36px;
        padding: 0;
        border-radius: 10px;
        font-size: 1rem;
        line-height: 1;
      }
      #${MODAL_ID} .kcm-nav-count {
        min-width: 64px;
        text-align: center;
        font-size: 0.84rem;
        font-weight: 700;
        color: var(--text-muted);
      }
      #${MODAL_ID} #kcm-alerts {
        display: grid;
        gap: 0.75rem;
      }
      #${MODAL_ID} #kcm-body {
        min-height: 0;
        overflow: auto;
        padding-right: 0.2rem;
        align-content: start;
      }
      #${MODAL_ID} .kcm-callout {
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.22);
        background: color-mix(in srgb, var(--surface2) 90%, white 2%);
        padding: 0.95rem 1rem;
        color: var(--text);
        line-height: 1.55;
      }
      #${MODAL_ID} .kcm-callout[data-tone="warning"] {
        border-color: rgba(245, 158, 11, 0.32);
        background: color-mix(in srgb, #f59e0b 10%, var(--surface2));
      }
      #${MODAL_ID} .kcm-callout[data-tone="danger"] {
        border-color: rgba(245, 83, 83, 0.32);
        background: color-mix(in srgb, #ef4444 10%, var(--surface2));
      }
      #${MODAL_ID} .kcm-section {
        display: grid;
        gap: 0.55rem;
      }
      #${MODAL_ID} .kcm-merchant-layout {
        display: grid;
        grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
        gap: 1rem;
        align-items: start;
      }
      #${MODAL_ID} .kcm-merchant-main,
      #${MODAL_ID} .kcm-merchant-side {
        display: grid;
        gap: 1rem;
        min-width: 0;
      }
      #${MODAL_ID} .kcm-section-title {
        font-size: 0.98rem;
        font-weight: 700;
        color: var(--text);
      }
      #${MODAL_ID} .kcm-entry-card {
        display: grid;
        gap: 0.45rem;
        padding: 1rem 1.05rem;
        border-radius: 14px;
        border: 1px solid rgba(124, 130, 255, 0.24);
        background:
          linear-gradient(135deg, rgba(124, 130, 255, 0.12), rgba(255, 209, 102, 0.06)),
          color-mix(in srgb, var(--surface2) 90%, white 2%);
      }
      #${MODAL_ID} .kcm-entry-label {
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #c9d2ff;
      }
      #${MODAL_ID} .kcm-entry-text {
        font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
        font-size: 1.1rem;
        font-weight: 700;
        line-height: 1.45;
        color: #fff5cb;
        word-break: break-word;
      }
      #${MODAL_ID} .kcm-entry-normalized {
        font-size: 0.82rem;
        color: var(--text-muted);
      }
      #${MODAL_ID} .kcm-entry-normalized code {
        color: #d9e2ff;
      }
      #${MODAL_ID} .kcm-bullets {
        margin: 0;
        padding-left: 1.15rem;
        color: var(--text-muted);
        display: grid;
        gap: 0.4rem;
        line-height: 1.55;
      }
      #${MODAL_ID} .kcm-toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        flex-wrap: wrap;
      }
      #${MODAL_ID} .kcm-selection-copy {
        font-size: 0.84rem;
        color: var(--text-muted);
      }
      #${MODAL_ID} .kcm-toggle-row {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
      }
      #${MODAL_ID} .kcm-toggle-btn {
        min-width: 88px;
      }
      #${MODAL_ID} .kcm-option-grid {
        display: grid;
        gap: 0.7rem;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }
      #${MODAL_ID} .kcm-option {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        gap: 0.8rem;
        align-items: start;
        padding: 0.9rem 1rem;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: color-mix(in srgb, var(--surface2) 92%, white 2%);
        cursor: pointer;
        margin: 0;
        text-transform: none;
        letter-spacing: normal;
        font-weight: 500;
        transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
      }
      #${MODAL_ID} .kcm-option:hover {
        border-color: rgba(124, 130, 255, 0.28);
        background: rgba(124, 130, 255, 0.06);
      }
      #${MODAL_ID} .kcm-option.is-checked {
        border-color: rgba(124, 130, 255, 0.42);
        background: rgba(124, 130, 255, 0.1);
        box-shadow: inset 0 0 0 1px rgba(124, 130, 255, 0.12);
      }
      #${MODAL_ID} .kcm-option input[type="checkbox"] {
        width: 18px;
        height: 18px;
        margin-top: 0.18rem;
        accent-color: var(--accent);
      }
      #${MODAL_ID} .kcm-option-copy {
        display: grid;
        gap: 0.2rem;
      }
      #${MODAL_ID} .kcm-option-title {
        font-size: 0.92rem;
        font-weight: 700;
        color: var(--text);
      }
      #${MODAL_ID} .kcm-option-meta {
        font-size: 0.8rem;
        color: var(--text-muted);
        line-height: 1.4;
      }
      #${MODAL_ID} .kcm-match-grid {
        display: grid;
        gap: 0.6rem;
      }
      #${MODAL_ID} .kcm-match-card {
        border-radius: 12px;
        border: 1px solid var(--border);
        background: color-mix(in srgb, var(--surface2) 92%, white 2%);
        padding: 0.8rem 0.95rem;
      }
      #${MODAL_ID} .kcm-match-line {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        flex-wrap: wrap;
        font-size: 0.9rem;
        line-height: 1.5;
        color: var(--text);
      }
      #${MODAL_ID} .kcm-token {
        display: inline-flex;
        align-items: center;
        min-height: 30px;
        padding: 0.1rem 0.7rem;
        border-radius: 999px;
        font-size: 0.84rem;
        font-weight: 700;
        line-height: 1.2;
      }
      #${MODAL_ID} .kcm-token-keyword {
        background: rgba(255, 209, 102, 0.12);
        border: 1px solid rgba(255, 209, 102, 0.24);
        color: #ffe8ac;
      }
      #${MODAL_ID} .kcm-token-category {
        background: rgba(124, 130, 255, 0.12);
        border: 1px solid rgba(124, 130, 255, 0.24);
        color: #d9deff;
      }
      #${MODAL_ID} .kcm-arrow {
        color: var(--text-muted);
        font-weight: 700;
      }
      #${MODAL_ID} .kcm-inline-note {
        font-size: 0.8rem;
        color: var(--text-muted);
        line-height: 1.55;
      }
      #${MODAL_ID} .kcm-category-label {
        display: block;
        margin-bottom: 0.45rem;
        font-size: 0.95rem;
        font-weight: 700;
        color: var(--text);
        text-transform: none;
        letter-spacing: normal;
      }
      #${MODAL_ID} #kcm-category-select {
        font-size: 1rem;
        padding: 0.55rem 0.75rem;
      }
      #${MODAL_ID} .kcm-actions {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
        margin-top: 0;
        padding-top: 0.85rem;
        border-top: 1px solid rgba(148, 163, 184, 0.12);
        background: linear-gradient(180deg, rgba(19, 22, 42, 0), rgba(19, 22, 42, 0.92) 40%);
      }
      #${MODAL_ID} .kcm-actions .btn {
        min-height: 40px;
        padding: 0.28rem 0.8rem;
        border-radius: 12px;
        font-size: 0.96rem;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        box-shadow: none;
      }
      #${MODAL_ID} .kcm-btn-neutral {
        background: linear-gradient(180deg, color-mix(in srgb, var(--surface3, #273362) 86%, white 14%), color-mix(in srgb, var(--surface3, #273362) 94%, black 6%));
        color: var(--text);
        border: 1px solid color-mix(in srgb, var(--accent) 34%, var(--border));
      }
      #${MODAL_ID} .kcm-btn-neutral:hover {
        border-color: color-mix(in srgb, var(--accent) 52%, white 8%);
        background: linear-gradient(180deg, color-mix(in srgb, var(--surface3, #273362) 78%, white 22%), color-mix(in srgb, var(--surface3, #273362) 90%, black 10%));
      }
      #${MODAL_ID} .kcm-btn-muted {
        background: rgba(124, 130, 255, 0.08);
        color: var(--text);
        border: 1px solid rgba(124, 130, 255, 0.18);
      }
      #${MODAL_ID} .kcm-btn-muted:hover {
        color: #f7f8ff;
        border-color: rgba(124, 130, 255, 0.36);
        background: rgba(124, 130, 255, 0.15);
      }
      #${MODAL_ID} .kcm-btn-action {
        background: linear-gradient(180deg, #dc2626, #b91c1c);
        color: #fff;
        border: 1px solid rgba(239, 68, 68, 0.5);
      }
      #${MODAL_ID} .kcm-btn-action:hover {
        background: linear-gradient(180deg, #ef4444, #dc2626);
        border-color: rgba(239, 68, 68, 0.7);
      }
      #${MODAL_ID} .kcm-conflict-list {
        display: grid;
        gap: 0.5rem;
      }
      #${MODAL_ID} .kcm-conflict-row {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding: 0.7rem 0.9rem;
        border-radius: 10px;
        border: 1px solid var(--border);
        background: color-mix(in srgb, var(--surface2) 92%, white 2%);
        cursor: pointer;
        flex-wrap: wrap;
      }
      #${MODAL_ID} .kcm-conflict-row.is-checked {
        border-color: rgba(239, 68, 68, 0.3);
        background: rgba(239, 68, 68, 0.06);
      }
      #${MODAL_ID} .kcm-conflict-keywords {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        flex: 1;
        flex-wrap: wrap;
      }
      #${MODAL_ID} .kcm-conflict-row input[type="checkbox"] {
        width: 18px;
        height: 18px;
        margin-left: auto;
        flex-shrink: 0;
        accent-color: #ef4444;
      }
      #${MODAL_ID} .kcm-btn-primary {
        background: color-mix(in srgb, var(--accent) 78%, white 22%);
        color: #fff;
        border: 1px solid rgba(124, 130, 255, 0.45);
      }
      #${MODAL_ID} .kcm-btn-primary:hover {
        filter: brightness(1.04);
      }
      #${MODAL_ID} .kcm-merchant-side .kcm-option-grid {
        grid-template-columns: 1fr;
      }
      @media (max-width: 920px) {
        #${MODAL_ID} .modal {
          width: min(96vw, 760px);
          max-width: 760px;
        }
        #${MODAL_ID} .kcm-merchant-layout {
          grid-template-columns: 1fr;
        }
      }
      @media (max-width: 680px) {
        #${MODAL_ID} .modal {
          width: min(96vw, 100%);
          max-height: 94vh;
          padding: 1rem;
        }
        #${MODAL_ID} .kcm-header {
          align-items: stretch;
        }
        #${MODAL_ID} .kcm-nav {
          width: 100%;
          justify-content: flex-end;
        }
        #${MODAL_ID} .kcm-actions {
          grid-template-columns: 1fr;
        }
        #${MODAL_ID} .kcm-option-grid {
          grid-template-columns: 1fr;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function injectModal() {
    if (document.getElementById(MODAL_ID)) return;
    injectStyles();
    document.body.insertAdjacentHTML("beforeend", `
      <div class="modal-overlay hidden" id="${MODAL_ID}">
        <div class="modal">
          <div class="kcm-header">
            <h2 id="kcm-title">Keyword Review</h2>
            <div id="kcm-nav" class="kcm-nav"></div>
          </div>
          <div id="kcm-alerts"></div>
          <div id="kcm-body" style="display:grid;gap:1rem"></div>
          <div class="kcm-actions" id="kcm-actions"></div>
        </div>
      </div>
    `);

    document.getElementById(MODAL_ID).addEventListener("click", (e) => {
      if (e.target === document.getElementById(MODAL_ID)) {
        closeCurrent({ action: "cancel", removals: [] });
      }
    });
  }

  let _resolver = null;

  function clearAlerts() {
    const alerts = document.getElementById("kcm-alerts");
    if (alerts) alerts.innerHTML = "";
  }

  function closeCurrent(result) {
    const modal = document.getElementById(MODAL_ID);
    if (modal) modal.classList.add("hidden");
    clearAlerts();
    if (_resolver) {
      const resolve = _resolver;
      _resolver = null;
      resolve(result);
    }
  }

  function selectedRemovalItems() {
    return [...document.querySelectorAll("#kcm-body input[data-removal-key]:checked")].map((el) => ({
      categoryId: +(el.dataset.categoryId || 0),
      categoryName: el.dataset.categoryName || "",
      keyword: el.dataset.keyword || "",
    }));
  }

  function setActions(buttons) {
    const host = document.getElementById("kcm-actions");
    host.innerHTML = "";
    const cols = Math.max(1, Math.min(buttons.length || 1, 3));
    host.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
    for (const btn of buttons) {
      const el = document.createElement("button");
      el.type = "button";
      el.className = btn.className || "btn kcm-btn-neutral";
      el.textContent = btn.label;
      el.addEventListener("click", btn.onClick);
      host.appendChild(el);
    }
  }

  function setNav({
    current = 1,
    total = 1,
    onPrev = null,
    onNext = null,
  } = {}) {
    const host = document.getElementById("kcm-nav");
    if (!host) return;
    if (!total || total < 2) {
      host.innerHTML = "";
      return;
    }
    host.innerHTML = `
      <button type="button" class="btn btn-secondary btn-sm kcm-nav-btn" id="kcm-nav-prev"${onPrev ? "" : " disabled"} aria-label="Previous conflict">←</button>
      <span class="kcm-nav-count">${escHtml(current)} / ${escHtml(total)}</span>
      <button type="button" class="btn btn-secondary btn-sm kcm-nav-btn" id="kcm-nav-next"${onNext ? "" : " disabled"} aria-label="Next conflict">→</button>
    `;
    if (onPrev) {
      document.getElementById("kcm-nav-prev")?.addEventListener("click", onPrev);
    }
    if (onNext) {
      document.getElementById("kcm-nav-next")?.addEventListener("click", onNext);
    }
  }

  function renderRemovalChecklist(removals, emptyLabel) {
    if (!removals.length) {
      return `<div class="text-muted" style="font-size:0.85rem">${escHtml(emptyLabel)}</div>`;
    }
    return `
      <div class="kcm-toolbar">
        <div class="kcm-selection-copy" id="kcm-selection-copy"></div>
        <div class="kcm-toggle-row">
          <button type="button" class="btn btn-ghost btn-sm kcm-toggle-btn" id="kcm-select-all">Select all</button>
          <button type="button" class="btn btn-ghost btn-sm kcm-toggle-btn" id="kcm-clear-all">Clear all</button>
        </div>
      </div>
      <div class="kcm-option-grid">
        ${removals.map((item) => `
          <label class="kcm-option">
            <input type="checkbox"
              data-removal-key="${escHtml(item.categoryId + "|" + item.keyword)}"
              data-category-id="${escHtml(item.categoryId)}"
              data-category-name="${escHtml(item.categoryName)}"
              data-keyword="${escHtml(item.keyword)}"
              checked />
            <span class="kcm-option-copy">
              <span class="kcm-option-title">Remove "${escHtml(item.keyword)}"</span>
              <span class="kcm-option-meta">From <strong>${escHtml(item.categoryName)}</strong></span>
            </span>
          </label>
        `).join("")}
      </div>
    `;
  }

  function updateRemovalSelectionUi() {
    const checkboxes = [...document.querySelectorAll("#kcm-body input[data-removal-key]")];
    checkboxes.forEach((checkbox) => {
      checkbox.closest(".kcm-option")?.classList.toggle("is-checked", checkbox.checked);
    });
    const count = checkboxes.filter((checkbox) => checkbox.checked).length;
    const copy = document.getElementById("kcm-selection-copy");
    if (copy) {
      copy.textContent = `${count} of ${checkboxes.length} selected.`;
    }
  }

  function bindRemovalChecklist(onChange) {
    const checkboxes = [...document.querySelectorAll("#kcm-body input[data-removal-key]")];
    if (!checkboxes.length) return;
    const selectAllBtn = document.getElementById("kcm-select-all");
    const clearAllBtn = document.getElementById("kcm-clear-all");
    if (selectAllBtn) {
      selectAllBtn.addEventListener("click", () => {
        checkboxes.forEach((checkbox) => { checkbox.checked = true; });
        updateRemovalSelectionUi();
        if (typeof onChange === "function") onChange();
      });
    }
    if (clearAllBtn) {
      clearAllBtn.addEventListener("click", () => {
        checkboxes.forEach((checkbox) => { checkbox.checked = false; });
        updateRemovalSelectionUi();
        if (typeof onChange === "function") onChange();
      });
    }
    checkboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        updateRemovalSelectionUi();
        if (typeof onChange === "function") onChange();
      });
    });
    updateRemovalSelectionUi();
  }

  function openKeywordDraftConflictModal({
    title,
    categories,
    draftKeywords,
    excludeCategoryId,
    onCategoriesUpdated,
  }) {
    injectModal();
    const modal = document.getElementById(MODAL_ID);
    const body = document.getElementById("kcm-body");
    let currentCategories = categories || [];
    document.getElementById("kcm-title").textContent = title || "Keyword conflicts";
    setNav();
    modal.classList.remove("hidden");

    const promise = new Promise((resolve) => {
      _resolver = resolve;
    });

    async function renderDraftConflicts() {
      clearAlerts();
      const analysis = CategoryKeywordTools.analyzeDraftKeywordConflicts(
        currentCategories,
        draftKeywords,
        excludeCategoryId
      );
      const hasExact = !!analysis.exact.length;
      const hasOverlap = !!analysis.overlaps.length;

      if (!hasExact && !hasOverlap) {
        closeCurrent({ action: "resolved", removals: [], categories: currentCategories });
        return;
      }

      body.innerHTML = `
        <div class="kcm-callout" data-tone="${hasExact ? "danger" : "warning"}">
          ${hasExact
            ? "These keywords already exist on other categories."
            : "These keywords overlap saved keywords on other categories."}
        </div>
        ${hasExact ? `
          <div class="kcm-section">
            <div class="kcm-section-title">Duplicates</div>
            <ul class="kcm-bullets">
              ${analysis.exact.map((item) => `<li>${escHtml(item.note)}</li>`).join("")}
            </ul>
          </div>
        ` : ""}
        ${hasOverlap ? `
          <div class="kcm-section">
            <div class="kcm-section-title">Overlaps</div>
            <ul class="kcm-bullets">
              ${analysis.overlaps.map((item) => `<li>${escHtml(item.note)}</li>`).join("")}
            </ul>
          </div>
        ` : ""}
        <div class="kcm-section">
          <div class="kcm-section-title">Remove saved keywords</div>
          ${renderRemovalChecklist(
            analysis.removalCandidates || [],
            "There are no saved keywords to remove for this set of conflicts."
          )}
        </div>
      `;
      bindRemovalChecklist();

      setActions([
        {
          label: "Back",
          className: "btn kcm-btn-neutral",
          onClick: () => closeCurrent({ action: "cancel", removals: [], categories: currentCategories }),
        },
        ...(!hasExact ? [{
          label: "Keep for now",
          className: "btn kcm-btn-muted",
          onClick: () => closeCurrent({ action: "save_anyway", removals: [], categories: currentCategories }),
        }] : []),
        {
          label: "Remove selected keywords",
          className: "btn kcm-btn-primary",
          onClick: async () => {
            const removals = selectedRemovalItems();
            if (!removals.length) {
              showAlert(
                document.getElementById("kcm-alerts"),
                hasExact
                  ? "Pick at least one conflicting keyword to remove, or go back and edit the draft."
                  : "Pick at least one keyword to remove, or use Save anyway.",
                "error"
              );
              return;
            }
            try {
              currentCategories = await CategoryKeywordTools.removeKeywords(removals);
              if (typeof onCategoriesUpdated === "function") {
                await onCategoriesUpdated(currentCategories);
              }
              await renderDraftConflicts();
            } catch (err) {
              showAlert(
                document.getElementById("kcm-alerts"),
                err?.message || "Could not remove the selected keywords.",
                "error"
              );
            }
          },
        },
      ]);
    }

    renderDraftConflicts();
    return promise;
  }

  function openMerchantKeywordModal({
    title,
    merchantName,
    normalizedMerchant,
    matches,
    selectedCategory,
    navigation,
    onApplyRemovals,
  }) {
    injectModal();
    const modal = document.getElementById(MODAL_ID);
    const body = document.getElementById("kcm-body");
    const uniqueCategories = [...new Set((matches || []).map((item) => item.categoryName))].sort();
    const currentCategory = selectedCategory || uniqueCategories[0] || "";
    const removalCandidates = CategoryKeywordTools.uniqueBy(
      (matches || []).map((item) => ({
        categoryId: item.categoryId,
        categoryName: item.categoryName,
        keyword: item.keyword,
        length: item.length || 0,
      })),
      (item) => `${item.categoryId}|${item.keyword}`
    );
    const bestLength = removalCandidates.reduce((max, r) => Math.max(max, r.length), 0);
    const strongestIdx = (() => {
      const inCat = removalCandidates.findIndex((r) => r.categoryName === currentCategory && r.length === bestLength);
      return inCat >= 0 ? inCat : removalCandidates.findIndex((r) => r.length === bestLength);
    })();
    let allowRemoveAll = false;
    document.getElementById("kcm-title").textContent = title || "Keyword matches";
    setNav({
      current: navigation?.current || 1,
      total: navigation?.total || 1,
      onPrev: navigation?.hasPrev
        ? () => closeCurrent({
          action: "prev",
          removals: [],
          selectedCategory: document.getElementById("kcm-category-select")?.value || currentCategory,
        })
        : null,
      onNext: navigation?.hasNext
        ? () => closeCurrent({
          action: "next",
          removals: [],
          selectedCategory: document.getElementById("kcm-category-select")?.value || currentCategory,
        })
        : null,
    });
    clearAlerts();

    body.innerHTML = `
      <div class="kcm-entry-card">
        <div class="kcm-entry-label">Entry</div>
        <div class="kcm-entry-text">${escHtml(merchantName || "Untitled entry")}</div>
        <div class="kcm-entry-normalized"><em>Normalized match text:</em> <code>${escHtml(normalizedMerchant || "") || "-"}</code></div>
      </div>
      <div class="kcm-section">
        <label class="kcm-category-label" for="kcm-category-select">Category for this row</label>
        <select id="kcm-category-select" class="review-inp" style="width:100%">
          ${uniqueCategories.map((name) => `
            <option value="${escHtml(name)}"${name === currentCategory ? " selected" : ""}>${escHtml(name)}</option>
          `).join("")}
        </select>
      </div>
      <div class="kcm-section">
        <div class="kcm-section-title">Keyword matches - check to remove</div>
        <div class="kcm-conflict-list">
          ${removalCandidates.map((item, i) => {
            const willRemove = item.categoryName !== currentCategory;
            return `
              <label class="kcm-conflict-row${willRemove ? " is-checked" : ""}">
                <span class="kcm-conflict-keywords">
                  <span class="kcm-token kcm-token-keyword">${escHtml(item.keyword)}</span>
                  <span class="kcm-arrow">→</span>
                  <span class="kcm-token kcm-token-category">${escHtml(item.categoryName)}</span>
                  ${i === strongestIdx ? `<span class="badge">strongest</span>` : ""}
                </span>
                <input type="checkbox"
                  data-removal-key="${escHtml(item.categoryId + "|" + item.keyword)}"
                  data-category-id="${escHtml(String(item.categoryId))}"
                  data-category-name="${escHtml(item.categoryName)}"
                  data-keyword="${escHtml(item.keyword)}"
                  ${willRemove ? "checked" : ""} />
              </label>
            `;
          }).join("")}
        </div>
        <div class="kcm-inline-note">Checked keywords will be removed from their category. Saves immediately.</div>
      </div>
    `;

    document.querySelectorAll("#kcm-body .kcm-conflict-row input[type='checkbox']").forEach((cb) => {
      cb.addEventListener("change", () => {
        cb.closest(".kcm-conflict-row")?.classList.toggle("is-checked", cb.checked);
        allowRemoveAll = false;
      });
    });

    document.getElementById("kcm-category-select")?.addEventListener("change", (e) => {
      const newCat = e.target.value;
      document.querySelectorAll("#kcm-body input[data-removal-key]").forEach((cb) => {
        cb.checked = cb.dataset.categoryName !== newCat;
        cb.closest(".kcm-conflict-row")?.classList.toggle("is-checked", cb.checked);
      });
      allowRemoveAll = false;
    });

    setActions([
      {
        label: "Close",
        className: "btn kcm-btn-neutral",
        onClick: () => closeCurrent({
          action: "close",
          removals: [],
          selectedCategory: document.getElementById("kcm-category-select")?.value || currentCategory,
        }),
      },
      {
        label: "Apply removals",
        className: "btn kcm-btn-action",
        onClick: async () => {
          const removals = selectedRemovalItems();
          if (!removals.length) {
            showAlert(document.getElementById("kcm-alerts"), "Pick at least one keyword to remove.", "error");
            return;
          }
          if (removalCandidates.length && removals.length === removalCandidates.length && !allowRemoveAll) {
            showAlert(
              document.getElementById("kcm-alerts"),
              "All matched keywords are selected. Keep one for auto-categorization. Click again to remove all.",
              "warning"
            );
            allowRemoveAll = true;
            return;
          }
          const selCat = document.getElementById("kcm-category-select")?.value || currentCategory;
          let updatedState = null;
          if (typeof onApplyRemovals === "function") {
            try {
              updatedState = await onApplyRemovals({ removals, selectedCategory: selCat });
            } catch (err) {
              showAlert(document.getElementById("kcm-alerts"), err?.message || "Could not remove keywords.", "error");
              return;
            }
          }
          closeCurrent({ action: "remove", removals, selectedCategory: selCat, updatedState });
        },
      },
      {
        label: "Use for this row",
        className: "btn kcm-btn-primary",
        onClick: () => {
          const selCat = document.getElementById("kcm-category-select")?.value || currentCategory;
          const body = document.getElementById("kcm-body");
          if (body) {
            body.style.transition = "opacity 0.18s ease";
            body.style.opacity = "0.35";
          }
          const actionBar = document.getElementById("kcm-actions");
          if (actionBar) {
            actionBar.querySelectorAll("button").forEach((b) => { b.disabled = true; });
          }
          const titleEl = document.getElementById("kcm-title");
          if (titleEl) {
            titleEl.textContent = `✓ Set to ${selCat}`;
            titleEl.style.color = "#22c55e";
          }
          setTimeout(() => {
            if (body) { body.style.transition = ""; body.style.opacity = ""; }
            if (titleEl) { titleEl.style.color = ""; }
            closeCurrent({ action: "done", removals: [], selectedCategory: selCat });
          }, 480);
        },
      },
    ]);

    modal.classList.remove("hidden");
    return new Promise((resolve) => {
      _resolver = resolve;
    });
  }

  async function resolveKeywordDraftConflicts({
    title,
    categories,
    draftKeywords,
    excludeCategoryId,
    onCategoriesUpdated,
  }) {
    const currentCategories = categories || [];
    const analysis = CategoryKeywordTools.analyzeDraftKeywordConflicts(
      currentCategories,
      draftKeywords,
      excludeCategoryId
    );
    if (!analysis.exact.length && !analysis.overlaps.length) {
      return { cancelled: false, categories: currentCategories };
    }
    const result = await openKeywordDraftConflictModal({
      title,
      categories: currentCategories,
      draftKeywords,
      excludeCategoryId,
      onCategoriesUpdated,
    });
    return {
      cancelled: result?.action === "cancel",
      categories: result?.categories || currentCategories,
    };
  }

  window.openKeywordDraftConflictModal = openKeywordDraftConflictModal;
  window.openMerchantKeywordModal = openMerchantKeywordModal;
  window.resolveKeywordDraftConflicts = resolveKeywordDraftConflicts;
})();
