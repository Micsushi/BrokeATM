(function () {
  const MODAL_ID = "category-picker-modal";

  let resolvePicker = null;
  let pickerState = null;

  function getHost() {
    return document.getElementById(MODAL_ID);
  }

  function getPanel() {
    return document.querySelector(`#${MODAL_ID} .category-picker-modal`);
  }

  function positionPopover() {
    if (!pickerState || pickerState.mode !== "popover") return;
    const panel = getPanel();
    const anchorEl = pickerState.anchorEl;
    if (!panel || !anchorEl || !document.body.contains(anchorEl)) {
      closeCategoryPickerModal(null);
      return;
    }

    const margin = 12;
    const gap = 8;
    const rect = anchorEl.getBoundingClientRect();
    const maxWidth = Math.max(280, Math.min(420, window.innerWidth - margin * 2));
    const width = Math.min(maxWidth, Math.max(rect.width, 300));
    const left = Math.min(
      Math.max(margin, rect.left),
      Math.max(margin, window.innerWidth - width - margin)
    );

    panel.style.width = `${width}px`;
    panel.style.left = `${left}px`;
    panel.style.top = `${rect.bottom + gap}px`;
    panel.style.maxHeight = `${Math.max(240, window.innerHeight - rect.bottom - gap - margin)}px`;

    const panelHeight = panel.offsetHeight;
    const belowSpace = window.innerHeight - rect.bottom - gap - margin;
    const aboveSpace = rect.top - gap - margin;
    let top = rect.bottom + gap;
    let maxHeight = belowSpace;

    if (panelHeight > belowSpace && aboveSpace > belowSpace) {
      maxHeight = aboveSpace;
      top = Math.max(margin, rect.top - gap - Math.min(panelHeight, aboveSpace));
    }

    panel.style.top = `${top}px`;
    panel.style.maxHeight = `${Math.max(220, maxHeight)}px`;
  }

  function ensureModal() {
    if (document.getElementById(MODAL_ID)) return;
    document.body.insertAdjacentHTML("beforeend", `
      <div class="modal-overlay hidden" id="${MODAL_ID}">
        <div class="modal category-picker-modal" role="dialog" aria-modal="true" aria-labelledby="category-picker-title">
          <div class="category-picker-header">
            <div>
              <h2 id="category-picker-title">Select category</h2>
              <p id="category-picker-copy" class="category-picker-copy hidden"></p>
            </div>
            <button class="btn btn-secondary btn-sm" id="category-picker-close" type="button">Close</button>
          </div>
          <input
            type="text"
            id="category-picker-search"
            class="category-picker-search"
            placeholder="Search categories..."
            aria-label="Search categories"
            autocomplete="off"
            spellcheck="false"
          />
          <div class="category-picker-meta" id="category-picker-meta"></div>
          <div class="category-picker-list" id="category-picker-list"></div>
        </div>
      </div>
    `);

    const host = getHost();
    host.addEventListener("click", (event) => {
      if (pickerState?.mode === "modal" && event.target === host) closeCategoryPickerModal(null);
    });
    document.getElementById("category-picker-close").addEventListener("click", () => closeCategoryPickerModal(null));
    document.getElementById("category-picker-search").addEventListener("input", (event) => {
      renderPicker(event.target.value);
      if (pickerState?.mode === "popover") requestAnimationFrame(positionPopover);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !getHost()?.classList.contains("hidden")) {
        closeCategoryPickerModal(null);
      }
    });
    document.addEventListener("pointerdown", (event) => {
      if (!pickerState || pickerState.mode !== "popover") return;
      const panel = getPanel();
      const anchorEl = pickerState.anchorEl;
      if (panel?.contains(event.target)) return;
      if (anchorEl?.contains?.(event.target)) return;
      closeCategoryPickerModal(null);
    });
    window.addEventListener("resize", () => {
      if (pickerState?.mode === "popover") positionPopover();
    });
    window.addEventListener("scroll", () => {
      if (pickerState?.mode === "popover") positionPopover();
    }, true);
  }

  function normalizeItem(item, index, actionLabel, selectedValue) {
    const name = String(item.name ?? item.label ?? "").trim();
    const description = String(item.description ?? item.subtitle ?? "").trim();
    const value = item.hasOwnProperty("value")
      ? item.value
      : item.hasOwnProperty("id")
        ? item.id
        : name;
    const key = String(item.key ?? `${value ?? "null"}:${index}`);
    const searchText = String(item.searchText ?? `${name} ${description}`).toLowerCase();
    return {
      ...item,
      name,
      description,
      value,
      key,
      actionText: item.actionText || actionLabel,
      isSelected: selectedValue !== undefined && value === selectedValue,
      searchText,
    };
  }

  function noResultsText(query) {
    const fn = pickerState?.noResultsMessage;
    if (typeof fn === "function") return fn(query);
    if (typeof fn === "string" && fn) return fn;
    return `No categories match "${query}".`;
  }

  function emptyResultsText() {
    return pickerState?.emptyMessage || "No categories available.";
  }

  function pickerResult(item) {
    return {
      ...item,
      id: item.hasOwnProperty("id") ? item.id : null,
      value: item.value,
      name: item.name,
      color: item.color || "",
      description: item.description || "",
    };
  }

  function renderPicker(query = "") {
    if (!pickerState) return;
    const normalized = String(query || "").trim().toLowerCase();
    const list = document.getElementById("category-picker-list");
    const meta = document.getElementById("category-picker-meta");
    const filtered = pickerState.items.filter((item) => {
      if (!normalized) return true;
      return item.searchText.includes(normalized);
    });

    meta.textContent = filtered.length === 0
      ? "No categories found."
      : `${filtered.length} categor${filtered.length === 1 ? "y" : "ies"} available`;

    if (!filtered.length) {
      list.innerHTML = normalized
        ? `<div class="category-picker-empty">${escHtml(noResultsText(query))}</div>`
        : `<div class="category-picker-empty">${escHtml(emptyResultsText())}</div>`;
      return;
    }

    list.innerHTML = filtered.map((item) => {
      const dot = item.color
        ? `<span class="category-picker-dot" style="background:${escHtml(item.color)}"></span>`
        : `<span class="category-picker-dot"></span>`;
      const action = item.isSelected
        ? `<span class="category-picker-current">Current</span>`
        : escHtml(item.actionText || "Select");
      return `
        <button
          type="button"
          class="category-picker-item"
          data-picker-key="${escHtml(item.key)}"
        >
          <span class="category-picker-item-main">
            <span class="category-picker-item-name">${dot}<span>${escHtml(item.name)}</span></span>
            <span class="category-picker-item-sub">${escHtml(item.description || "")}</span>
          </span>
          <span class="category-picker-item-action">${action}</span>
        </button>
      `;
    }).join("");

    list.querySelectorAll("[data-picker-key]").forEach((button) => {
      button.addEventListener("click", () => {
        const item = pickerState.items.find((entry) => entry.key === button.dataset.pickerKey);
        closeCategoryPickerModal(item ? pickerResult(item) : null);
      });
    });
  }

  function closeCategoryPickerModal(result = null) {
    const host = getHost();
    const panel = getPanel();
    if (host) host.classList.add("hidden");
    if (panel) {
      panel.style.removeProperty("width");
      panel.style.removeProperty("left");
      panel.style.removeProperty("top");
      panel.style.removeProperty("max-height");
    }
    pickerState = null;
    if (resolvePicker) {
      const resolve = resolvePicker;
      resolvePicker = null;
      resolve(result);
    }
  }

  function openCategoryPickerModal(options = {}) {
    ensureModal();
    if (resolvePicker) closeCategoryPickerModal(null);

    const {
      title = "Select category",
      subtitle = "",
      searchPlaceholder = "Search categories...",
      items = [],
      noneOption = null,
      actionLabel = "Select",
      selectedValue,
      emptyMessage = "No categories available.",
      noResultsMessage = null,
      mode = "modal",
      anchorEl = null,
    } = options;
    const actualMode = mode === "popover" && anchorEl ? "popover" : "modal";

    const combined = [];
    if (noneOption) {
      combined.push({
        key: "__none__",
        id: null,
        value: null,
        name: noneOption.label || "No category",
        description: noneOption.description || "",
        color: "",
        actionText: noneOption.actionText || actionLabel,
      });
    }
    items.forEach((item) => combined.push(item));

    pickerState = {
      items: combined.map((item, index) => normalizeItem(item, index, actionLabel, selectedValue)),
      emptyMessage,
      noResultsMessage,
      mode: actualMode,
      anchorEl,
    };

    const host = getHost();
    const panel = getPanel();
    host.className = actualMode === "popover" ? "category-picker-popover-shell" : "modal-overlay";
    panel.className = actualMode === "popover"
      ? "modal category-picker-modal category-picker-popover"
      : "modal category-picker-modal";
    document.getElementById("category-picker-close").classList.toggle("hidden", actualMode === "popover");
    document.getElementById("category-picker-title").textContent = title;
    const copy = document.getElementById("category-picker-copy");
    copy.textContent = subtitle || "";
    copy.classList.toggle("hidden", !subtitle);
    const search = document.getElementById("category-picker-search");
    search.value = "";
    search.placeholder = searchPlaceholder;

    renderPicker("");
    host.classList.remove("hidden");
    requestAnimationFrame(() => {
      if (actualMode === "popover") positionPopover();
      search.focus();
      search.select();
    });

    return new Promise((resolve) => {
      resolvePicker = resolve;
    });
  }

  window.openCategoryPickerModal = openCategoryPickerModal;
  window.closeCategoryPickerModal = closeCategoryPickerModal;
})();
