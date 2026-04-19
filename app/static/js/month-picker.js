class MonthPicker {
  constructor(containerId, { mode = 'single', onChange = () => {} } = {}) {
    this.el = document.getElementById(containerId);
    this.mode = mode;
    this.onChange = onChange;
    this._months = [];
    this._active = mode === 'multi' ? new Set() : 0;
    this._bindWheelScroll();
  }

  render(months, initial) {
    this._months = months;
    if (initial !== undefined) this._active = initial;
    this._build();
  }

  setActive(active) {
    this._active = active;
    this._sync();
  }

  get selected() { return this._active; }


  _build() {
    this.el.innerHTML = '';
    this._months.forEach((m, i) => {
      const btn = document.createElement('button');
      btn.className = 'month-chip';
      btn.textContent = m.label;
      btn.dataset.ym = m.ym;
      btn.dataset.idx = String(i);
      this._applySelected(btn, i, m.ym);
      btn.addEventListener('click', () => this._onClick(btn, i, m.ym));
      this.el.appendChild(btn);
    });
  }

  _applySelected(btn, i, ym) {
    const on = this.mode === 'multi' ? this._active.has(ym) : this._active === i;
    btn.classList.toggle('selected', on);
  }

  _sync() {
    this.el.querySelectorAll('.month-chip').forEach((btn, i) => {
      this._applySelected(btn, i, btn.dataset.ym);
    });
  }

  _onClick(btn, i, ym) {
    if (this.mode === 'multi') {
      if (this._active.has(ym)) this._active.delete(ym);
      else this._active.add(ym);
      btn.classList.toggle('selected', this._active.has(ym));
      this.onChange(this._active);
    } else {
      this._active = i;
      this._sync();
      this.onChange(i, ym);
    }
  }

  _bindWheelScroll() {
    if (!this.el) return;
    this.el.addEventListener('wheel', (event) => {
      if (event.ctrlKey || this.el.scrollWidth <= this.el.clientWidth) return;

      const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
      if (!delta) return;

      const maxScrollLeft = this.el.scrollWidth - this.el.clientWidth;
      const nextScrollLeft = Math.max(0, Math.min(maxScrollLeft, this.el.scrollLeft + delta));
      if (nextScrollLeft === this.el.scrollLeft) return;

      event.preventDefault();
      this.el.scrollLeft = nextScrollLeft;
    }, { passive: false });
  }
}
