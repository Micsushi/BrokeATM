function renderDateRangeFilterBlock(targetId, {
  fromId,
  toId,
  allId = "",
  clearId = "",
  actionId = "",
  fromLabel = "From",
  toLabel = "To",
  allLabel = "All",
  clearLabel = "Clear",
  actionLabel = "All dates",
  fromTitle = "From",
  toTitle = "To",
  allTitle = "Show all dates",
  clearTitle = "Clear dates",
  actionTitle = "Show all dates",
  wrapperClass = "",
  allButtonClass = "btn btn-secondary btn-sm picker-action-btn",
  clearButtonClass = "btn btn-ghost btn-sm picker-action-btn",
  actionButtonClass = "btn btn-secondary btn-sm picker-action-btn",
} = {}) {
  const target = document.getElementById(targetId);
  if (!target) return;
  const rowClassName = ["picker-range-row", wrapperClass].filter(Boolean).join(" ");

  const primaryActionId = allId || actionId;
  const primaryActionLabel = allId ? allLabel : actionLabel;
  const primaryActionTitle = allId ? allTitle : actionTitle;
  const primaryActionClass = allId ? allButtonClass : actionButtonClass;
  const actionButtons = [];

  if (primaryActionId) {
    actionButtons.push(
      `<button class="${primaryActionClass}" id="${primaryActionId}" type="button" title="${primaryActionTitle}">${primaryActionLabel}</button>`
    );
  }
  if (clearId) {
    actionButtons.push(
      `<button class="${clearButtonClass}" id="${clearId}" type="button" title="${clearTitle}">${clearLabel}</button>`
    );
  }

  const actionMarkup = actionButtons.length
    ? `
        <div class="picker-range-actions">
          ${actionButtons.join("")}
        </div>
      `
    : "";

  target.innerHTML = `
    <div class="${rowClassName}">
      <input type="month" id="${fromId}" title="${fromTitle}" aria-label="${fromLabel}" />
      <span class="picker-range-sep">→</span>
      <input type="month" id="${toId}" title="${toTitle}" aria-label="${toLabel}" />
      ${actionMarkup}
    </div>
  `;
}

function renderMonthFilterSection(targetId, {
  prefix,
  title,
  includeCard = true,
  containerClass = "",
} = {}) {
  const target = document.getElementById(targetId);
  if (!target) return;

  const wrapperClass = includeCard
    ? `card mb-2 ${containerClass}`.trim()
    : containerClass;

  target.innerHTML = `
    <div class="${wrapperClass}">
      <div class="picker-card-header">
        <span class="section-title">${title}</span>
      </div>
      <div class="picker-range-row">
        <input type="month" id="${prefix}-range-from" title="From month" />
        <span class="picker-range-sep">→</span>
        <input type="month" id="${prefix}-range-to" title="To month" />
        <div class="picker-range-actions">
          <button class="btn btn-secondary btn-sm picker-action-btn" id="${prefix}-all" type="button">All</button>
          <button class="btn btn-ghost btn-sm picker-action-btn" id="${prefix}-clear" type="button">Clear</button>
        </div>
      </div>
      <div class="picker-scroll-outer">
        <div class="month-picker" id="${prefix}-picker"></div>
      </div>
    </div>
  `;
}

class MonthFilterGroup {
  constructor(prefix, {
    selectedSet,
    getAvailableMonths = () => [],
    onChange = () => {},
  } = {}) {
    this.prefix = prefix;
    this.selectedSet = selectedSet || new Set();
    this.getAvailableMonths = getAvailableMonths;
    this.onChange = onChange;

    this.allBtn = document.getElementById(`${prefix}-all`);
    this.clearBtn = document.getElementById(`${prefix}-clear`);
    this.fromEl = document.getElementById(`${prefix}-range-from`);
    this.toEl = document.getElementById(`${prefix}-range-to`);
    this.picker = new MonthPicker(`${prefix}-picker`, {
      mode: "multi",
      onChange: () => {
        this.syncControls();
        this.onChange(this.selectedSet);
      },
    });

    this._bindEvents();
  }

  render(months) {
    this._pruneSelection();
    this.picker.render(months, this.selectedSet);
    this.syncControls();
  }

  refresh() {
    this._pruneSelection();
    this.picker.setActive(this.selectedSet);
    this.syncControls();
  }

  syncControls() {
    this._syncCtrlChips();
    this._syncRangeInputs();
  }

  selectAll() {
    this.selectedSet.clear();
    this.getAvailableMonths().forEach(({ ym }) => this.selectedSet.add(ym));
    this.picker.setActive(this.selectedSet);
    this.syncControls();
    this.onChange(this.selectedSet);
  }

  clear() {
    this.selectedSet.clear();
    this.picker.setActive(this.selectedSet);
    this.syncControls();
    this.onChange(this.selectedSet);
  }

  _bindEvents() {
    this.allBtn?.addEventListener("click", () => this.selectAll());
    this.clearBtn?.addEventListener("click", () => this.clear());

    const applyRange = () => {
      const from = this.fromEl?.value || "";
      const to = this.toEl?.value || "";
      this._applyRange(from, to);
    };

    this.fromEl?.addEventListener("change", applyRange);
    this.toEl?.addEventListener("change", applyRange);
  }

  _selectionRange() {
    if (this.selectedSet.size === 0) return [null, null];
    const sorted = [...this.selectedSet].sort();
    return [sorted[0], sorted[sorted.length - 1]];
  }

  _isContiguous() {
    if (this.selectedSet.size === 0) return true;
    const [minYm, maxYm] = this._selectionRange();
    const inRange = this.getAvailableMonths().filter(({ ym }) => ym >= minYm && ym <= maxYm);
    return inRange.every(({ ym }) => this.selectedSet.has(ym));
  }

  _syncRangeInputs() {
    if (!this.fromEl || !this.toEl) return;

    if (this.selectedSet.size === 0 || !this._isContiguous()) {
      this.fromEl.value = "";
      this.toEl.value = "";
      return;
    }

    const [minYm, maxYm] = this._selectionRange();
    this.fromEl.value = minYm || "";
    this.toEl.value = maxYm || "";
  }

  _applyRange(fromYm, toYm) {
    this.selectedSet.clear();

    this.getAvailableMonths().forEach(({ ym }) => {
      if ((!fromYm || ym >= fromYm) && (!toYm || ym <= toYm)) {
        this.selectedSet.add(ym);
      }
    });

    this.picker.setActive(this.selectedSet);
    this.syncControls();
    this.onChange(this.selectedSet);
  }

  _syncCtrlChips() {
    if (!this.allBtn) return;

    const availableMonths = this.getAvailableMonths();
    const allSelected =
      availableMonths.length > 0 &&
      this.selectedSet.size === availableMonths.length &&
      availableMonths.every(({ ym }) => this.selectedSet.has(ym));

    this.allBtn.classList.toggle("active", allSelected);
    this.clearBtn?.classList.remove("active");
  }

  _pruneSelection() {
    const availableYms = new Set(this.getAvailableMonths().map(({ ym }) => ym));
    [...this.selectedSet].forEach((ym) => {
      if (!availableYms.has(ym)) this.selectedSet.delete(ym);
    });
  }
}
