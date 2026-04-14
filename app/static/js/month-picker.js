/**
 * MonthPicker — reusable scrollable month chip selector.
 *
 * Modes:
 *   'single'  one chip active at a time; onChange(idx, ym)
 *   'multi'   toggle chips into/out of a Set; onChange(selectedSet<ym>)
 *
 * HTML contract: pass the id of a .month-picker element that is already
 * wrapped in .picker-scroll-outer. The component owns only the inner div.
 *
 * Usage (single):
 *   const p = new MonthPicker('month-chips', {
 *     mode: 'single',
 *     onChange: (idx, ym) => { ... }
 *   });
 *   p.render([{ label: 'Apr 2026', ym: '2026-04' }, ...], 0);
 *
 * Usage (multi):
 *   const p = new MonthPicker('pie-picker', {
 *     mode: 'multi',
 *     onChange: (set) => { ... }
 *   });
 *   const sel = new Set(['2026-04', '2026-03']);
 *   p.render([{ label, ym }, ...], sel);
 *   p.setActive(sel);  // re-sync after external changes (All / Clear buttons)
 */
class MonthPicker {
  constructor(containerId, { mode = 'single', onChange = () => {} } = {}) {
    this.el = document.getElementById(containerId);
    this.mode = mode;
    this.onChange = onChange;
    this._months = [];
    this._active = mode === 'multi' ? new Set() : 0;
  }

  /** Rebuild chips. initial: idx (single) or Set<ym> (multi). */
  render(months, initial) {
    this._months = months;
    if (initial !== undefined) this._active = initial;
    this._build();
  }

  /** Sync visual state after external selection changes — no DOM rebuild. */
  setActive(active) {
    this._active = active;
    this._sync();
  }

  /** Current selection: idx (single) or Set<ym> (multi). */
  get selected() { return this._active; }

  // ── private ────────────────────────────────────────────────────────────────

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
}
