(function () {
  function normalizeMatchText(value) {
    return String(value || "")
      .toLocaleLowerCase()
      .replace(/[_\p{P}\p{S}\s]+/gu, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function dedupe(list) {
    return [...new Set(list)];
  }

  function parseKeywordText(raw) {
    return dedupe(
      String(raw || "")
        .split(/[\n,]/)
        .map((part) => normalizeMatchText(part))
        .filter(Boolean)
    );
  }

  function parseCommittedKeywordText(raw) {
    const text = String(raw || "");
    if (!text) return [];
    if (/[\n,]\s*$/.test(text)) {
      return parseKeywordText(text);
    }
    return parseKeywordText(text.replace(/[^,\n]*$/, ""));
  }

  function parseKeywordCsv(raw) {
    return dedupe(
      String(raw || "")
        .split(",")
        .map((part) => normalizeMatchText(part))
        .filter(Boolean)
    );
  }

  function categoryKeywordEntries(categories) {
    const entries = [];
    for (const cat of categories || []) {
      for (const keyword of parseKeywordCsv(cat.keywords || "")) {
        entries.push({
          categoryId: cat.id ?? null,
          categoryName: String(cat.name || "").trim().toLowerCase(),
          keyword,
          length: keyword.length,
        });
      }
    }
    entries.sort((a, b) =>
      (b.length - a.length) ||
      a.categoryName.localeCompare(b.categoryName) ||
      a.keyword.localeCompare(b.keyword)
    );
    return entries;
  }

  function uniqueBy(items, getKey) {
    const seen = new Set();
    return items.filter((item) => {
      const key = getKey(item);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function analyzeDraftKeywordConflicts(categories, draftKeywords, excludeCategoryId = null) {
    const keywords = dedupe((draftKeywords || []).map((kw) => normalizeMatchText(kw)).filter(Boolean));
    const entries = categoryKeywordEntries(categories).filter((entry) => entry.categoryId !== excludeCategoryId);
    const exact = [];
    const overlaps = [];
    const seenExact = new Set();
    const seenOverlap = new Set();

    for (const keyword of keywords) {
      for (const entry of entries) {
        if (entry.keyword === keyword) {
          const key = [keyword, entry.categoryId, entry.categoryName].join("|");
          if (seenExact.has(key)) continue;
          seenExact.add(key);
          exact.push({
            candidateKeyword: keyword,
            otherKeyword: entry.keyword,
            categoryId: entry.categoryId,
            categoryName: entry.categoryName,
            note: `"${keyword}" is already saved on "${entry.categoryName}".`,
          });
          continue;
        }
        if (!entry.keyword.includes(keyword) && !keyword.includes(entry.keyword)) continue;
        const key = [keyword, entry.keyword, entry.categoryId, entry.categoryName].join("|");
        if (seenOverlap.has(key)) continue;
        seenOverlap.add(key);
        const note = entry.keyword.includes(keyword)
          ? `"${keyword}" may get mixed up with "${entry.keyword}" in "${entry.categoryName}".`
          : `"${entry.keyword}" in "${entry.categoryName}" may capture merchants meant for "${keyword}".`;
        overlaps.push({
          candidateKeyword: keyword,
          otherKeyword: entry.keyword,
          categoryId: entry.categoryId,
          categoryName: entry.categoryName,
          note,
        });
      }
    }

    return {
      exact,
      overlaps,
      removalCandidates: uniqueBy(
        [...exact, ...overlaps].map((item) => ({
          categoryId: item.categoryId,
          categoryName: item.categoryName,
          keyword: item.otherKeyword,
        })),
        (item) => `${item.categoryId}|${item.keyword}`
      ),
    };
  }

  function analyzeMerchantKeywordMatches(merchantName, categories) {
    const normalizedMerchant = normalizeMatchText(merchantName);
    const matches = categoryKeywordEntries(categories).filter((entry) =>
      entry.keyword && normalizedMerchant.includes(entry.keyword)
    );
    const uniqueCategories = dedupe(matches.map((item) => item.categoryName));
    const categoryCount = uniqueCategories.length;
    const longestLength = matches.length ? matches[0].length : 0;
    const longestMatches = matches.filter((item) => item.length === longestLength);
    const suggestedCategory = longestMatches.length
      ? dedupe(longestMatches.map((item) => item.categoryName)).sort()[0]
      : null;
    return {
      normalizedMerchant,
      keywordMatches: matches,
      keywordResolutionNeeded: categoryCount > 1,
      keywordConflictCategories: categoryCount > 1,
      suggestedCategory,
    };
  }

  async function removeKeywords(removals) {
    const clean = uniqueBy(
      (removals || []).filter((item) => item && item.categoryId != null && item.keyword).map((item) => ({
        categoryId: item.categoryId,
        keyword: normalizeMatchText(item.keyword),
      })),
      (item) => `${item.categoryId}|${item.keyword}`
    );
    if (!clean.length) {
      return API.getCategories();
    }

    const categories = await API.getCategories();
    const removalsByCategory = new Map();
    for (const item of clean) {
      const list = removalsByCategory.get(item.categoryId) || [];
      list.push(item.keyword);
      removalsByCategory.set(item.categoryId, list);
    }

    await Promise.all(
      categories
        .filter((cat) => removalsByCategory.has(cat.id))
        .map((cat) => {
          const toRemove = new Set(removalsByCategory.get(cat.id));
          const remaining = parseKeywordCsv(cat.keywords || "").filter((keyword) => !toRemove.has(keyword));
          return API.updateCategory(cat.id, { keywords: remaining.join(", ") || null });
        })
    );

    return API.getCategories();
  }

  window.CategoryKeywordTools = {
    analyzeDraftKeywordConflicts,
    analyzeMerchantKeywordMatches,
    categoryKeywordEntries,
    normalizeMatchText,
    parseCommittedKeywordText,
    parseKeywordCsv,
    parseKeywordText,
    removeKeywords,
    uniqueBy,
  };
})();
