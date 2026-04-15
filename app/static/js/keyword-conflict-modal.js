(function () {
  const MODAL_ID = "keyword-conflict-modal";
  const STYLE_ID = "keyword-conflict-modal-styles";
  const TOAST_ID = "keyword-conflict-toast";

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${MODAL_ID} .modal {
        width: min(96vw, 1040px);
        max-width: 1040px;
        max-height: min(92vh, 920px);
        display: grid;
        grid-template-rows: auto auto minmax(0, 1fr) auto;
        gap: 0.85rem;
        padding: 1.25rem 1.45rem 1rem;
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
        min-width: 40px;
        min-height: 40px;
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
        align-items: stretch;
      }
      #${MODAL_ID} .kcm-merchant-full {
        grid-column: 1 / -1;
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
        min-height: 164px;
        height: 100%;
        align-content: start;
        border-radius: 14px;
        border: 1px solid rgba(124, 130, 255, 0.24);
        background:
          linear-gradient(135deg, rgba(124, 130, 255, 0.12), rgba(255, 209, 102, 0.06)),
          color-mix(in srgb, var(--surface2) 90%, white 2%);
      }
      #${MODAL_ID} .kcm-choice-card {
        display: grid;
        align-content: start;
        gap: 0.9rem;
        padding: 1rem 1.05rem;
        min-height: 164px;
        height: 100%;
        border-radius: 14px;
        border: 1px solid rgba(124, 130, 255, 0.24);
        background:
          linear-gradient(135deg, rgba(124, 130, 255, 0.12), rgba(124, 130, 255, 0.04)),
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
      #${MODAL_ID} .kcm-toolbar-sub {
        align-items: flex-end;
        margin-top: -0.15rem;
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
        gap: 0.6rem;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }
      #${MODAL_ID} .kcm-option {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        gap: 0.8rem;
        align-items: center;
        padding: 0.9rem 1rem;
        min-height: 96px;
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
        margin-top: 0;
        accent-color: var(--accent);
      }
      #${MODAL_ID} .kcm-option-copy {
        display: grid;
        gap: 0.3rem;
        align-content: center;
      }
      #${MODAL_ID} .kcm-option-label {
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        color: var(--text-muted);
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
        padding: 0.9rem 1rem;
        min-height: 96px;
        display: grid;
        align-content: center;
      }
      #${MODAL_ID} .kcm-match-scroll {
        display: grid;
        gap: 0.55rem;
        max-height: min(44vh, 360px);
        overflow: auto;
        padding-right: 0.2rem;
      }
      #${MODAL_ID} .kcm-merchant-row {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
        gap: 1rem;
        min-height: 68px;
        padding: 0.72rem 1.15rem;
        border-radius: 12px;
        border: 1px solid rgba(124, 130, 255, 0.24);
        background:
          linear-gradient(135deg, rgba(124, 130, 255, 0.12), rgba(124, 130, 255, 0.04)),
          color-mix(in srgb, var(--surface2) 90%, white 2%);
        cursor: pointer;
      }
      #${MODAL_ID} .kcm-merchant-row:hover {
        border-color: rgba(124, 130, 255, 0.24);
        background:
          linear-gradient(135deg, rgba(124, 130, 255, 0.12), rgba(124, 130, 255, 0.04)),
          color-mix(in srgb, var(--surface2) 90%, white 2%);
      }
      #${MODAL_ID} .kcm-merchant-row.is-checked {
        border-color: rgba(124, 130, 255, 0.24);
        background:
          linear-gradient(135deg, rgba(124, 130, 255, 0.12), rgba(124, 130, 255, 0.04)),
          color-mix(in srgb, var(--surface2) 90%, white 2%);
        box-shadow: none;
      }
      #${MODAL_ID} .kcm-merchant-summary {
        display: grid;
        grid-template-columns: minmax(0, 272px) 48px minmax(0, 272px) auto;
        align-items: center;
        column-gap: 0.85rem;
        row-gap: 0.45rem;
        min-width: 0;
        width: 100%;
      }
      #${MODAL_ID} .kcm-merchant-piece {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        align-items: center;
        gap: 0.45rem;
        min-width: 0;
        white-space: nowrap;
      }
      #${MODAL_ID} .kcm-value-slot {
        display: flex;
        align-items: center;
        min-width: 0;
        width: 100%;
      }
      #${MODAL_ID} .kcm-inline-key {
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--text-muted);
      }
      #${MODAL_ID} .kcm-merchant-remove {
        display: inline-flex;
        align-items: center;
        gap: 0.55rem;
        font-size: 0.88rem;
        font-weight: 700;
        color: var(--text);
        white-space: nowrap;
      }
      #${MODAL_ID} .kcm-merchant-remove input[type="checkbox"] {
        width: 18px;
        height: 18px;
        accent-color: var(--accent);
      }
      #${MODAL_ID} .kcm-match-row {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto;
        align-items: center;
        gap: 0.75rem;
      }
      #${MODAL_ID} .kcm-match-block {
        display: grid;
        gap: 0.35rem;
        min-width: 0;
      }
      #${MODAL_ID} .kcm-match-label {
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        color: var(--text-muted);
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
        min-height: 28px;
        padding: 0.1rem 0.68rem;
        border-radius: 999px;
        font-size: 0.76rem;
        font-weight: 700;
        line-height: 1.2;
        min-width: 0;
        width: fit-content;
        max-width: 100%;
      }
      #${MODAL_ID} .kcm-token-keyword {
        background: rgba(124, 130, 255, 0.12);
        border: 1px solid rgba(124, 130, 255, 0.24);
        color: #d9deff;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 100%;
      }
      #${MODAL_ID} .kcm-token-category {
        background: rgba(124, 130, 255, 0.12);
        border: 1px solid rgba(124, 130, 255, 0.24);
        color: #d9deff;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 100%;
      }
      #${MODAL_ID} .kcm-strongest-badge {
        display: inline-flex;
        align-items: center;
        justify-self: start;
        min-height: 28px;
        padding: 0.1rem 0.68rem;
        border-radius: 999px;
        background: rgba(255, 209, 102, 0.16);
        border: 1px solid rgba(255, 209, 102, 0.28);
        color: #ffe3a0;
        font-size: 0.72rem;
        font-weight: 800;
        line-height: 1.2;
        white-space: nowrap;
      }
      #${MODAL_ID} .kcm-arrow {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 48px;
        color: var(--text-muted);
        font-weight: 700;
        font-size: 1.2rem;
      }
      #${MODAL_ID} #kcm-category-select {
        min-height: 48px;
        padding: 0.72rem 0.95rem;
        font-size: 1.14rem;
        font-weight: 600;
      }
      #${MODAL_ID} .kcm-inline-note {
        font-size: 0.8rem;
        color: var(--text-muted);
        line-height: 1.55;
      }
      #${MODAL_ID} .kcm-category-label {
        display: block;
        margin-bottom: 0.45rem;
        font-size: 0.84rem;
        font-weight: 700;
        color: var(--text);
        text-transform: none;
        letter-spacing: normal;
      }
      #${MODAL_ID} .kcm-actions {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
        margin-top: 0;
        padding-top: 0.35rem;
        border-top: 1px solid rgba(148, 163, 184, 0.12);
        background: linear-gradient(180deg, rgba(19, 22, 42, 0), rgba(19, 22, 42, 0.92) 40%);
      }
      #${MODAL_ID} .kcm-actions .btn {
        min-height: 48px;
        border-radius: 12px;
        font-size: 0.96rem;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        box-shadow: none;
      }
      #${MODAL_ID} .kcm-merchant-side .kcm-option-grid {
        grid-template-columns: 1fr;
      }
      #${TOAST_ID} {
        position: fixed;
        bottom: 1.5rem;
        right: 1.5rem;
        background: var(--accent);
        color: #fff;
        padding: 0.5rem 1.1rem;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.85rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4);
        z-index: 999;
        opacity: 0;
        transition: opacity 0.2s;
        pointer-events: none;
      }
      #${TOAST_ID}.show {
        opacity: 1;
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
        #${MODAL_ID} .kcm-merchant-row {
          grid-template-columns: 1fr;
          align-items: start;
        }
        #${MODAL_ID} .kcm-merchant-summary {
          grid-template-columns: 1fr;
          gap: 0.65rem;
        }
        #${MODAL_ID} .kcm-merchant-piece {
          white-space: normal;
        }
        #${MODAL_ID} .kcm-arrow {
          width: auto;
          justify-content: flex-start;
        }
        #${MODAL_ID} .kcm-merchant-remove {
          justify-self: start;
        }
        #${MODAL_ID} .kcm-match-row {
          grid-template-columns: 1fr;
          gap: 0.55rem;
        }
        #${TOAST_ID} {
          right: 1rem;
          bottom: 1rem;
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
      <div id="${TOAST_ID}" aria-live="polite"></div>
    `);

    document.getElementById(MODAL_ID).addEventListener("click", (e) => {
      if (e.target === document.getElementById(MODAL_ID)) {
        closeCurrent({ action: "cancel", removals: [] });
      }
    });
  }

  let _resolver = null;
  let _toastTimer = null;

  function clearAlerts() {
    const alerts = document.getElementById("kcm-alerts");
    if (alerts) alerts.innerHTML = "";
  }

  function showToast(message) {
    const toast = document.getElementById(TOAST_ID);
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => toast.classList.remove("show"), 1500);
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
      el.className = btn.className || "btn btn-secondary";
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
          <button type="button" class="btn btn-ghost btn-sm kcm-toggle-btn" id="kcm-select-all">Select All</button>
          <button type="button" class="btn btn-ghost btn-sm kcm-toggle-btn" id="kcm-clear-all">Clear All</button>
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
              <span class="kcm-option-label">Keyword</span>
              <span class="kcm-option-title">${escHtml(item.keyword)}</span>
              <span class="kcm-option-meta">Category <strong>${escHtml(item.categoryName)}</strong></span>
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
    document.getElementById("kcm-title").textContent = title || "Review keyword conflicts";
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
            ? "These keywords already exist in other categories."
            : "These keywords may overlap saved keywords in other categories."}
        </div>
        ${hasExact ? `
          <div class="kcm-section">
            <div class="kcm-section-title">Exact duplicates</div>
            <ul class="kcm-bullets">
              ${analysis.exact.map((item) => `<li>${escHtml(item.note)}</li>`).join("")}
            </ul>
          </div>
        ` : ""}
        ${hasOverlap ? `
          <div class="kcm-section">
            <div class="kcm-section-title">Possible overlaps</div>
            <ul class="kcm-bullets">
              ${analysis.overlaps.map((item) => `<li>${escHtml(item.note)}</li>`).join("")}
            </ul>
          </div>
        ` : ""}
        <div class="kcm-section">
          <div class="kcm-section-title">Remove saved keywords</div>
          ${renderRemovalChecklist(
            analysis.removalCandidates || [],
            "No saved keywords to remove."
          )}
        </div>
      `;
      bindRemovalChecklist();

      setActions([
        {
          label: "Back",
          className: "btn btn-secondary",
          onClick: () => closeCurrent({ action: "cancel", removals: [], categories: currentCategories }),
        },
        ...(!hasExact ? [{
          label: "Keep for now",
          className: "btn btn-ghost",
          onClick: () => closeCurrent({ action: "save_anyway", removals: [], categories: currentCategories }),
        }] : []),
        {
          label: "Remove selected",
          className: "btn btn-danger",
          onClick: async () => {
            const removals = selectedRemovalItems();
            if (!removals.length) {
              showAlert(
                document.getElementById("kcm-alerts"),
                hasExact
                  ? "Select a conflicting keyword to remove, or go back."
                  : "Select a keyword to remove, or keep these for now.",
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
                err?.message || "Couldn't remove the selected keywords.",
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
    rowIsDuplicate,
    rowExcluded,
    navigation,
    onApplyRemovals,
  }) {
    injectModal();
    const modal = document.getElementById(MODAL_ID);
    const body = document.getElementById("kcm-body");
    let currentMatches = [...(matches || [])];
    let currentNavigation = navigation || {};
    let currentCategory = selectedCategory || "";
    let currentRowIsDuplicate = !!rowIsDuplicate;
    let currentRowExcluded = !!rowExcluded;
    let allowRemoveAll = false;
    document.getElementById("kcm-title").textContent = title || "Review matches";
    clearAlerts();

    const promise = new Promise((resolve) => {
      _resolver = resolve;
    });

    function renderMerchantRows(uniqueCategories, bestLength) {
      return currentMatches.map((item) => {
        const checked = item.categoryName !== currentCategory;
        return `
          <label class="kcm-merchant-row${checked ? " is-checked" : ""}">
            <span class="kcm-merchant-summary">
              <span class="kcm-merchant-piece">
                <span class="kcm-inline-key">Keyword:</span>
                <span class="kcm-value-slot">
                  <span class="kcm-token kcm-token-keyword" title="${escHtml(item.keyword)}">${escHtml(item.keyword)}</span>
                </span>
              </span>
              <span class="kcm-arrow">→</span>
              <span class="kcm-merchant-piece">
                <span class="kcm-inline-key">Category:</span>
                <span class="kcm-value-slot">
                  <span class="kcm-token kcm-token-category" title="${escHtml(item.categoryName)}">${escHtml(item.categoryName)}</span>
                </span>
              </span>
              ${item.length === bestLength ? `<span class="kcm-strongest-badge">strongest match</span>` : ""}
            </span>
            <span class="kcm-merchant-remove">
              <input type="checkbox"
                data-removal-key="${escHtml(item.categoryId + "|" + item.keyword)}"
                data-category-id="${escHtml(item.categoryId)}"
                data-category-name="${escHtml(item.categoryName)}"
                data-keyword="${escHtml(item.keyword)}"
                ${checked ? "checked" : ""} />
              <span>Remove</span>
            </span>
          </label>
        `;
      }).join("");
    }

    function applySelectedCategoryDefaults() {
      const selected = document.getElementById("kcm-category-select")?.value || currentCategory;
      currentCategory = selected;
      const checkboxes = [...document.querySelectorAll("#kcm-body input[data-removal-key]")];
      checkboxes.forEach((checkbox) => {
        checkbox.checked = (checkbox.dataset.categoryName || "") !== selected;
      });
      updateRemovalSelectionUi();
      allowRemoveAll = false;
    }

    async function handleApplyRemovals() {
      const removals = selectedRemovalItems();
      if (!removals.length) {
        showAlert(document.getElementById("kcm-alerts"), "Select at least one keyword.", "error");
        return;
      }
      if (currentMatches.length && removals.length === currentMatches.length && !confirm(
        "Remove all matched keywords? This row will be uncategorized."
      )) {
        return;
      }
      if (typeof onApplyRemovals !== "function") {
        closeCurrent({
          action: "remove",
          removals,
          selectedCategory: document.getElementById("kcm-category-select")?.value || currentCategory,
        });
        return;
      }
      try {
        const nextState = await onApplyRemovals({
          removals,
          selectedCategory: document.getElementById("kcm-category-select")?.value || currentCategory,
        });
        if (nextState?.toastMessage) {
          showToast(nextState.toastMessage);
        }
        if (nextState?.status === "multiple") {
          currentMatches = [...(nextState.matches || currentMatches)];
          currentCategory = nextState.selectedCategory || currentCategory;
          currentNavigation = nextState.navigation || currentNavigation;
          currentRowIsDuplicate = !!nextState.rowIsDuplicate;
          currentRowExcluded = !!nextState.rowExcluded;
          renderMerchantState();
          return;
        }
        closeCurrent({
          action: "done",
          removals: [],
          selectedCategory: nextState?.selectedCategory || "",
        });
      } catch (err) {
        showAlert(
          document.getElementById("kcm-alerts"),
          err?.message || "Couldn't remove the selected keywords.",
          "error"
        );
      }
    }

    function renderMerchantState() {
      const uniqueCategories = [...new Set(currentMatches.map((item) => item.categoryName))].sort();
      if (!uniqueCategories.includes(currentCategory)) {
        currentCategory = uniqueCategories[0] || "";
      }
      const bestLength = currentMatches.length ? currentMatches[0].length : 0;
      clearAlerts();
      setNav({
        current: currentNavigation?.current || 1,
        total: currentNavigation?.total || 1,
        onPrev: currentNavigation?.hasPrev
          ? () => closeCurrent({
            action: "prev",
            removals: [],
            selectedCategory: document.getElementById("kcm-category-select")?.value || currentCategory,
          })
          : null,
        onNext: currentNavigation?.hasNext
          ? () => closeCurrent({
            action: "next",
            removals: [],
            selectedCategory: document.getElementById("kcm-category-select")?.value || currentCategory,
          })
          : null,
      });

      body.innerHTML = `
        <div class="kcm-merchant-layout">
          <div class="kcm-entry-card">
            <div class="kcm-entry-label">Entry</div>
            <div class="kcm-entry-text">${escHtml(merchantName || "Untitled entry")}</div>
            <div class="kcm-entry-normalized">Normalized text for matching: <code>${escHtml(normalizedMerchant || "") || "—"}</code></div>
          </div>
          <div class="kcm-choice-card">
            <div class="kcm-entry-label">Select category</div>
            <select id="kcm-category-select" class="review-inp" style="width:100%">
              ${uniqueCategories.map((name) => `
                <option value="${escHtml(name)}"${name === currentCategory ? " selected" : ""}>${escHtml(name)}</option>
              `).join("")}
            </select>
          </div>
          <div class="kcm-section kcm-merchant-full">
            <div class="kcm-toolbar">
              <div class="kcm-section-title">Matches</div>
            </div>
            <div class="kcm-toolbar kcm-toolbar-sub">
              <div class="kcm-selection-copy" id="kcm-selection-copy"></div>
              <div class="kcm-toggle-row">
                <button type="button" class="btn btn-ghost btn-sm kcm-toggle-btn" id="kcm-select-all">Select All</button>
                <button type="button" class="btn btn-ghost btn-sm kcm-toggle-btn" id="kcm-clear-all">Clear All</button>
              </div>
            </div>
            <div class="kcm-match-scroll">
              ${renderMerchantRows(uniqueCategories, bestLength)}
            </div>
          </div>
        </div>
      `;

      bindRemovalChecklist(() => {
        allowRemoveAll = false;
      });
      document.getElementById("kcm-category-select")?.addEventListener("change", applySelectedCategoryDefaults);
      updateRemovalSelectionUi();

      setActions([
        {
          label: "Close",
          className: "btn btn-secondary",
          onClick: () => closeCurrent({
            action: "close",
            removals: [],
            selectedCategory: document.getElementById("kcm-category-select")?.value || currentCategory,
          }),
        },
        {
          label: "Apply removals",
          className: "btn btn-danger",
          onClick: handleApplyRemovals,
        },
        {
          label: "Use category",
          className: "btn btn-primary",
          onClick: () => closeCurrent({
            action: "done",
            removals: [],
            selectedCategory: document.getElementById("kcm-category-select")?.value || currentCategory,
          }),
        },
      ]);
    }

    renderMerchantState();
    modal.classList.remove("hidden");
    return promise;
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
