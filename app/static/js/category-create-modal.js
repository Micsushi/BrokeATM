(function () {
  const MODAL_ID = "category-create-modal";

  function injectModal() {
    if (document.getElementById(MODAL_ID)) return;
    document.body.insertAdjacentHTML("beforeend", `
      <div class="modal-overlay hidden" id="${MODAL_ID}">
        <div class="modal" style="max-width:640px">
          <h2>Create Category</h2>
          <div id="ccm-alerts"></div>
          <div style="display:grid;gap:0.9rem">
            <div>
              <label>Name</label>
              <input type="text" id="ccm-name" placeholder="e.g. groceries" />
            </div>
            <div>
              <label>Keywords <span class="text-caption" style="font-weight:400;color:var(--text-muted);text-transform:none;letter-spacing:normal">(one per line)</span></label>
              <textarea class="mono-textarea" id="ccm-keywords" rows="5"
                style="resize:vertical"
                placeholder="e.g. fruit&#10;e.g. veggies"></textarea>
            </div>
            <div style="display:flex;align-items:flex-end;gap:0.85rem;flex-wrap:wrap">
              <div>
                <label>Color</label>
                <input type="color" id="ccm-color" value="#6366f1" style="display:block;width:56px;height:38px;padding:0;border:none;background:none" />
              </div>
              <div class="text-meta text-muted" style="line-height:1.45">
                This uses the same checks as the Categories page, including duplicate-name checks and keyword conflict review.
              </div>
            </div>
          </div>
          <div class="modal-actions">
            <button class="btn btn-secondary" id="ccm-cancel">Cancel</button>
            <button class="btn btn-primary" id="ccm-save">Create</button>
          </div>
        </div>
      </div>
    `);

    document.getElementById("ccm-cancel").addEventListener("click", closeModal);
    document.getElementById(MODAL_ID).addEventListener("click", (e) => {
      if (e.target === document.getElementById(MODAL_ID)) closeModal();
    });
    document.getElementById("ccm-name").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        document.getElementById("ccm-save").click();
      }
    });
  }

  function closeModal() {
    document.getElementById(MODAL_ID)?.classList.add("hidden");
    document.getElementById("ccm-alerts").innerHTML = "";
  }

  async function createCategoryDraft({
    name,
    color,
    keywords,
    onCategoriesUpdated,
  }) {
    const normalizedName = String(name || "").trim().toLowerCase();
    if (!normalizedName) {
      throw new Error("Enter a category name.");
    }

    let categories = await API.getCategories();
    if (categories.some((cat) => cat.name === normalizedName)) {
      throw new Error(`A category named "${normalizedName}" already exists.`);
    }

    const resolved = await resolveKeywordDraftConflicts({
      title: `Review keyword conflicts for "${normalizedName}"`,
      categories,
      draftKeywords: keywords,
      excludeCategoryId: null,
      onCategoriesUpdated,
    });
    if (resolved.cancelled) {
      return { cancelled: true, category: null, categories: resolved.categories };
    }
    categories = resolved.categories;

    const created = await API.createCategory({
      name: normalizedName,
      color,
      keywords: keywords.join(", ") || null,
    });
    const refreshed = await API.getCategories();
    if (typeof onCategoriesUpdated === "function") {
      await onCategoriesUpdated(refreshed, created);
    }
    return { cancelled: false, category: created, categories: refreshed };
  }

  function openCategoryCreateModal(opts = {}) {
    injectModal();
    document.querySelector(`#${MODAL_ID} h2`).textContent = opts.title || "Create Category";
    document.getElementById("ccm-name").value = opts.prefillName || "";
    document.getElementById("ccm-keywords").value = opts.prefillKeywords || "";
    document.getElementById("ccm-color").value = opts.prefillColor || "#6366f1";
    document.getElementById("ccm-alerts").innerHTML = "";
    document.getElementById("ccm-save").textContent = opts.confirmLabel || "Create";
    document.getElementById(MODAL_ID).classList.remove("hidden");
    document.getElementById("ccm-name").focus();
    document.getElementById("ccm-name").select();

    return new Promise((resolve) => {
      const saveBtn = document.getElementById("ccm-save");
      const handler = async () => {
        saveBtn.disabled = true;
        try {
          const result = await createCategoryDraft({
            name: document.getElementById("ccm-name").value,
            color: document.getElementById("ccm-color").value,
            keywords: CategoryKeywordTools.parseKeywordText(document.getElementById("ccm-keywords").value),
            onCategoriesUpdated: opts.onCategoriesUpdated,
          });
          if (result.cancelled) return;
          closeModal();
          resolve(result.category);
        } catch (err) {
          showAlert(document.getElementById("ccm-alerts"), err.message || "Could not create category.", "error");
        } finally {
          saveBtn.disabled = false;
        }
      };

      saveBtn.onclick = handler;
      document.getElementById("ccm-cancel").onclick = () => {
        closeModal();
        resolve(null);
      };
      document.getElementById(MODAL_ID).onclick = (e) => {
        if (e.target === document.getElementById(MODAL_ID)) {
          closeModal();
          resolve(null);
        }
      };
    });
  }

  window.createCategoryDraft = createCategoryDraft;
  window.openCategoryCreateModal = openCategoryCreateModal;
})();
