function renderDateRangeFilterBlock(targetId, {
  fromId,
  toId,
  actionId,
  fromLabel = "From",
  toLabel = "To",
  actionLabel = "All dates",
  fromTitle = "From",
  toTitle = "To",
  actionTitle = "Show all dates",
  wrapperClass = "",
  actionButtonClass = "btn btn-secondary",
} = {}) {
  const target = document.getElementById(targetId);
  if (!target) return;

  target.innerHTML = `
    <div class="${wrapperClass}">
      <div class="filter-group">
        <label>${fromLabel}</label>
        <input type="month" id="${fromId}" title="${fromTitle}" />
      </div>
      <div class="filter-group">
        <label>${toLabel}</label>
        <input type="month" id="${toId}" title="${toTitle}" />
      </div>
      <div class="filter-group records-date-filter-action">
        <button class="${actionButtonClass}" id="${actionId}" type="button" title="${actionTitle}">${actionLabel}</button>
      </div>
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
