let parsedData = null
let reviewRows = []
let categories = []
let importFilename = ""
let isPdfMode = false
let selectedParserId = null
let parserResults = []

let importDocs = []
let activeDocId = null
let currentStep = 1
let doneSummary = null
let queueProcessing = false
let importDraftDbPromise = null
let draftSaveTimer = null
let draftSaveInFlight = false
let draftSaveQueued = false
let restoringDraft = false

const BASE_IMPORT_PATH = "/import"
const STEP_NAMES = { 1: "upload", 2: "parse", 3: "periods", 4: "review", 5: "done" }
const STEP_FROM_NAME = { upload: 1, parse: 2, periods: 3, review: 4, done: 5 }
const IMPORT_DRAFT_DB = "brokeatm-import-draft"
const IMPORT_DRAFT_DB_VERSION = 1
const IMPORT_DRAFT_STATE_KEY = "current"
const FP_MONTH_LABELS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
]

const alertsEl = document.getElementById("alerts")
const dropZone = document.getElementById("drop-zone")
const fileInput = document.getElementById("file-input")

function indexedDbAvailable() {
  return typeof window !== "undefined" && !!window.indexedDB
}

function openImportDraftDb() {
  if (!indexedDbAvailable()) return Promise.resolve(null)
  if (importDraftDbPromise) return importDraftDbPromise
  importDraftDbPromise = new Promise((resolve, reject) => {
    const request = window.indexedDB.open(IMPORT_DRAFT_DB, IMPORT_DRAFT_DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains("state")) db.createObjectStore("state", { keyPath: "id" })
      if (!db.objectStoreNames.contains("files")) db.createObjectStore("files", { keyPath: "id" })
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  }).catch((error) => {
    importDraftDbPromise = null
    throw error
  })
  return importDraftDbPromise
}

function idbTransactionComplete(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
    tx.onabort = () => reject(tx.error || new Error("IndexedDB transaction aborted."))
  })
}

function idbRequestResult(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

function cloneForDraft(value) {
  if (value == null) return value
  return JSON.parse(JSON.stringify(value))
}

function generatedDocNamePattern(name) {
  if (!name) return true
  return /^doc-\d+-[a-z0-9]+$/i.test(name) || /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(name)
}

function applyDocFilename(doc, nextFilename) {
  if (!doc) return
  const trimmed = (nextFilename || "").trim()
  if (!trimmed || doc.filename === trimmed) return
  const previous = doc.filename
  doc.filename = trimmed

  if (doc.parsedData) {
    if (Array.isArray(doc.parsedData.source_files) && doc.parsedData.source_files.length) {
      doc.parsedData.source_files = doc.parsedData.source_files.map((name) => (name === previous || !name ? trimmed : name))
    } else {
      doc.parsedData.source_files = [trimmed]
    }
    if (Array.isArray(doc.parsedData.rows)) {
      doc.parsedData.rows.forEach((row) => {
        if (!row.source_file || row.source_file === previous) row.source_file = trimmed
      })
    }
    if (doc.parsedData.perFilePeriod && previous && previous !== trimmed && Object.prototype.hasOwnProperty.call(doc.parsedData.perFilePeriod, previous)) {
      doc.parsedData.perFilePeriod[trimmed] = doc.parsedData.perFilePeriod[previous]
      delete doc.parsedData.perFilePeriod[previous]
    }
  }

  if (Array.isArray(doc.reviewRows)) {
    doc.reviewRows.forEach((row) => {
      if (!row.source_file || row.source_file === previous) row.source_file = trimmed
    })
  }

  if (Array.isArray(doc.parserResults)) {
    doc.parserResults.forEach((result) => {
      if (!Array.isArray(result.rows)) return
      result.rows.forEach((row) => {
        if (!row.source_file || row.source_file === previous) row.source_file = trimmed
      })
    })
  }
}

function serializeDocForDraft(doc) {
  return {
    id: doc.id,
    filename: doc.filename,
    status: doc.status,
    step: doc.step,
    periodReady: !!doc.periodReady,
    reviewReady: !!doc.reviewReady,
    isPdfMode: !!doc.isPdfMode,
    parserResults: cloneForDraft(doc.parserResults || []),
    selectedParserId: doc.selectedParserId || null,
    parsedData: cloneForDraft(doc.parsedData),
    reviewRows: cloneForDraft(doc.reviewRows || []),
    errorMessage: doc.errorMessage || "",
    hasStoredFile: !!(doc.file || doc.hasStoredFile),
  }
}

function buildDraftState() {
  syncActiveDocFromGlobals()
  return {
    id: IMPORT_DRAFT_STATE_KEY,
    activeDocId,
    currentStep,
    doneSummary: cloneForDraft(doneSummary),
    importDocs: importDocs.map((doc) => serializeDocForDraft(doc)),
    savedAt: Date.now(),
  }
}

async function persistDraftFiles(docs) {
  const db = await openImportDraftDb()
  if (!db || !docs.length) return
  const tx = db.transaction("files", "readwrite")
  const store = tx.objectStore("files")
  docs.forEach((doc) => {
    if (!doc || !doc.file) return
    store.put({ id: doc.id, file: doc.file, filename: doc.filename, savedAt: Date.now() })
    doc.hasStoredFile = true
  })
  await idbTransactionComplete(tx)
}

async function deleteDraftFiles(docIds) {
  const db = await openImportDraftDb()
  if (!db || !docIds.length) return
  const tx = db.transaction("files", "readwrite")
  const store = tx.objectStore("files")
  docIds.forEach((docId) => store.delete(docId))
  await idbTransactionComplete(tx)
}

async function getDraftFile(docId) {
  const db = await openImportDraftDb()
  if (!db) return null
  const tx = db.transaction("files", "readonly")
  const store = tx.objectStore("files")
  const record = await idbRequestResult(store.get(docId))
  await idbTransactionComplete(tx)
  return record && record.file ? record.file : null
}

async function getDraftFileMetaMap(docIds) {
  const db = await openImportDraftDb()
  if (!db || !docIds.length) return new Map()
  const tx = db.transaction("files", "readonly")
  const store = tx.objectStore("files")
  const requests = docIds.map((docId) => idbRequestResult(store.get(docId)).then((record) => [docId, record || null]))
  const entries = await Promise.all(requests)
  await idbTransactionComplete(tx)
  return new Map(entries)
}

async function persistImportDraftNow() {
  if (restoringDraft) return
  if (draftSaveInFlight) {
    draftSaveQueued = true
    return
  }
  draftSaveInFlight = true
  try {
    const db = await openImportDraftDb()
    if (!db) return

    const state = buildDraftState()
    if (!state.importDocs.length && !state.doneSummary) {
      const clearTx = db.transaction(["state", "files"], "readwrite")
      clearTx.objectStore("state").delete(IMPORT_DRAFT_STATE_KEY)
      clearTx.objectStore("files").clear()
      await idbTransactionComplete(clearTx)
      return
    }

    await persistDraftFiles(importDocs.filter((doc) => doc.file))
    const tx = db.transaction("state", "readwrite")
    tx.objectStore("state").put(state)
    await idbTransactionComplete(tx)
  } catch (_) {
    // Draft persistence is best-effort. Importing should still work even if storage is unavailable.
  } finally {
    draftSaveInFlight = false
    if (draftSaveQueued) {
      draftSaveQueued = false
      void persistImportDraftNow()
    }
  }
}

function scheduleDraftSave() {
  if (restoringDraft) return
  clearTimeout(draftSaveTimer)
  draftSaveTimer = setTimeout(() => {
    draftSaveTimer = null
    void persistImportDraftNow()
  }, 150)
}

function markDraftDirty() {
  syncActiveDocFromGlobals()
  scheduleDraftSave()
}

async function clearImportDraftStorage() {
  clearTimeout(draftSaveTimer)
  draftSaveTimer = null
  const db = await openImportDraftDb()
  if (!db) return
  const tx = db.transaction(["state", "files"], "readwrite")
  tx.objectStore("state").delete(IMPORT_DRAFT_STATE_KEY)
  tx.objectStore("files").clear()
  await idbTransactionComplete(tx)
}

async function ensureDocFileLoaded(doc) {
  if (!doc) throw new Error("No file selected.")
  if (doc.file) return doc.file
  if (!doc.hasStoredFile) {
    throw new Error("This file is no longer available. Add it again.")
  }
  const file = await getDraftFile(doc.id)
  if (!file) {
    doc.hasStoredFile = false
    throw new Error("This file is no longer available. Add it again.")
  }
  doc.file = file
  if (generatedDocNamePattern(doc.filename) || !doc.filename) {
    applyDocFilename(doc, file.name)
  }
  return file
}

async function restoreImportDraft() {
  const db = await openImportDraftDb()
  if (!db) return false

  const tx = db.transaction("state", "readonly")
  const store = tx.objectStore("state")
  const record = await idbRequestResult(store.get(IMPORT_DRAFT_STATE_KEY))
  await idbTransactionComplete(tx)
  if (!record || !record.importDocs || !record.importDocs.length) return false
  const fileMetaMap = await getDraftFileMetaMap(record.importDocs.map((doc) => doc.id))

  restoringDraft = true
  try {
    importDocs = record.importDocs.map((doc, index) => {
      const status = (doc.status === "processing" || doc.status === "queued") ? "queued" : doc.status
      const fileMeta = fileMetaMap.get(doc.id)
      const restoredDoc = {
        id: doc.id,
        file: null,
        filename: doc.filename,
        status,
        step: doc.step,
        periodReady: !!doc.periodReady,
        reviewReady: !!doc.reviewReady,
        isPdfMode: !!doc.isPdfMode,
        parserResults: doc.parserResults || [],
        selectedParserId: doc.selectedParserId || null,
        parsedData: doc.parsedData || null,
        reviewRows: doc.reviewRows || [],
        errorMessage: doc.status === "error" ? (doc.errorMessage || "") : "",
        hasStoredFile: !!doc.hasStoredFile,
      }
      const fallbackSourceFile =
        (restoredDoc.parsedData && Array.isArray(restoredDoc.parsedData.source_files) && restoredDoc.parsedData.source_files[0]) ||
        (restoredDoc.reviewRows[0] && restoredDoc.reviewRows[0].source_file) ||
        (fileMeta && fileMeta.filename) ||
        `Imported file ${index + 1}`
      if (generatedDocNamePattern(restoredDoc.filename) || !restoredDoc.filename) {
        applyDocFilename(restoredDoc, fallbackSourceFile)
      }
      if (
        restoredDoc.isPdfMode &&
        restoredDoc.status === "ready" &&
        (!restoredDoc.parserResults || !restoredDoc.parserResults.length)
      ) {
        if (restoredDoc.hasStoredFile) {
          restoredDoc.status = "queued"
          restoredDoc.step = 2
          restoredDoc.periodReady = false
          restoredDoc.reviewReady = false
          restoredDoc.parsedData = null
          restoredDoc.reviewRows = []
          restoredDoc.selectedParserId = null
          restoredDoc.errorMessage = ""
        } else if (restoredDoc.parsedData && restoredDoc.parsedData.rows && restoredDoc.parsedData.rows.length) {
          restoredDoc.periodReady = true
          restoredDoc.step = restoredDoc.reviewReady ? 4 : 3
        } else {
          restoredDoc.status = "error"
          restoredDoc.step = 2
          restoredDoc.errorMessage = "Add this file again to finish parsing."
        }
      }
      // Re-queue or error if parsers ran but ALL returned 0 rows (scanned/unreadable PDFs)
      if (
        restoredDoc.isPdfMode &&
        restoredDoc.status === "ready" &&
        restoredDoc.parserResults &&
        restoredDoc.parserResults.length > 0
      ) {
        const maxRestoredRows = restoredDoc.parserResults.reduce(
          (max, r) => Math.max(max, (r.rows || []).length), 0
        )
        if (maxRestoredRows === 0) {
          if (restoredDoc.hasStoredFile) {
            restoredDoc.status = "queued"
            restoredDoc.step = 2
            restoredDoc.periodReady = false
            restoredDoc.reviewReady = false
            restoredDoc.parsedData = null
            restoredDoc.reviewRows = []
            restoredDoc.selectedParserId = null
            restoredDoc.parserResults = []
            restoredDoc.errorMessage = ""
          } else {
            restoredDoc.status = "error"
            restoredDoc.step = 2
            restoredDoc.errorMessage = "No rows could be extracted from this file. It may be a scanned/image PDF that requires OCR, or an unsupported format."
          }
        }
      }
      if (restoredDoc.isPdfMode && restoredDoc.parserResults && restoredDoc.parserResults.length && !restoredDoc.selectedParserId) {
        const recommended = getParserInsightsFor(restoredDoc.parserResults).recommended || restoredDoc.parserResults[0]
        restoredDoc.selectedParserId = recommended ? recommended.parser_id : null
      }
      return restoredDoc
    })
    doneSummary = record.doneSummary || null

    const preferredDocId = record.activeDocId && getDocById(record.activeDocId) ? record.activeDocId : null
    activeDocId = preferredDocId || (importDocs[0] ? importDocs[0].id : null)
    currentStep = STEP_NAMES[record.currentStep] ? record.currentStep : 1
    if (activeDocId) {
      currentStep = clampBatchStep(currentStep)
    } else if (doneSummary) {
      currentStep = 5
    } else {
      currentStep = 1
    }
  } finally {
    restoringDraft = false
  }
  return true
}

function newDocId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID()
  }
  return `doc-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function isCsvFile(file) {
  return (((file && file.name) || "").toLowerCase()).endsWith(".csv")
}

function isPdfOrOfx(file) {
  const name = typeof file === "string" ? file : ((file && file.name) || "")
  const lower = name.toLowerCase()
  return lower.endsWith(".pdf") || lower.endsWith(".ofx") || lower.endsWith(".qfx")
}

function isSupportedImportFile(file) {
  return isCsvFile(file) || isPdfOrOfx(file)
}

function createImportDoc(file) {
  return {
    id: newDocId(),
    file,
    hasStoredFile: !!file,
    filename: file.name,
    status: "queued",
    step: 2,
    periodReady: isCsvFile(file),
    reviewReady: false,
    isPdfMode: isPdfOrOfx(file),
    parserResults: [],
    selectedParserId: null,
    parsedData: null,
    reviewRows: [],
    errorMessage: "",
  }
}

function getDocById(docId) {
  return importDocs.find((doc) => doc.id === docId) || null
}

function getActiveDoc() {
  return getDocById(activeDocId)
}

function getReadyDocs() {
  return importDocs.filter((doc) => doc.status === "ready")
}

function yieldToBrowser() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

function docsByStatus(statuses) {
  const wanted = Array.isArray(statuses) ? statuses : [statuses]
  return importDocs.filter((doc) => wanted.includes(doc.status))
}

function maxBatchStage() {
  if (!importDocs.length) return doneSummary ? 5 : 1
  if (docsByStatus(["queued", "processing", "error"]).length) return 2
  if (importDocs.some((doc) => doc.status !== "ready")) return 2
  if (importDocs.some((doc) => !doc.periodReady)) return 2
  if (importDocs.some((doc) => !doc.reviewReady)) return 3
  return 4
}

function clampBatchStep(requestedStep) {
  if (requestedStep === 1) return 1
  if (requestedStep === 5) {
    return !importDocs.length && doneSummary ? 5 : Math.min(4, maxBatchStage())
  }
  return Math.min(requestedStep, maxBatchStage())
}

function parseStageAdvanceState() {
  if (!importDocs.length) {
    return { disabled: true, label: "Add files to continue", reason: "No files in this batch yet." }
  }
  const blockingDocs = docsByStatus(["queued", "processing"])
  if (blockingDocs.length) {
    return {
      disabled: true,
      label: `Waiting for ${blockingDocs.length} file${blockingDocs.length !== 1 ? "s" : ""} to finish parsing`,
      reason: "Wait for parsing to finish before moving the whole batch forward.",
    }
  }
  const errorDocs = docsByStatus("error")
  if (errorDocs.length) {
    return {
      disabled: true,
      label: `Resolve or remove ${errorDocs.length} file${errorDocs.length !== 1 ? "s" : ""}`,
      reason: "Files with parse errors must be fixed or removed before the batch can continue.",
    }
  }
  const missingParser = importDocs.filter((doc) =>
    doc.isPdfMode && doc.status === "ready" && (!doc.parserResults || !doc.parserResults.length || !doc.selectedParserId)
  )
  if (missingParser.length) {
    return {
      disabled: true,
      label: `Choose parsers for ${missingParser.length} file${missingParser.length !== 1 ? "s" : ""}`,
      reason: "Pick a parser for every PDF/OFX file before continuing.",
    }
  }
  const hasPdf = importDocs.some((doc) => doc.isPdfMode)
  return {
    disabled: false,
    label: hasPdf ? "Use selected parser for all files →" : "Continue all files to file periods →",
    reason: "",
  }
}

function countInvalidSelectedRows(docs = getReadyDocs()) {
  let count = 0
  docs.forEach((doc) => {
    if (!prepareDocForReview(doc)) return
    doc.reviewRows.forEach((row) => {
      if (!row.exclude && rowMissingRequired(row).length) count += 1
    })
  })
  return count
}

function reviewStageActionState() {
  const readyDocs = getReadyDocs()
  if (!readyDocs.length) {
    return { disabled: true, label: "No reviewed files yet", reason: "Finish parsing and review before importing." }
  }
  const invalidCount = countInvalidSelectedRows(readyDocs)
  if (invalidCount) {
    return {
      disabled: true,
      label: `Fix ${invalidCount} row${invalidCount !== 1 ? "s" : ""} before importing`,
      reason: "Rows with missing required fields must be fixed or excluded first.",
    }
  }
  return { disabled: false, label: "Import all reviewed files", reason: "" }
}

function queuePrimaryActionState() {
  if (currentStep === 2) return parseStageAdvanceState()
  if (currentStep === 3) {
    return {
      disabled: !importDocs.length || docsByStatus(["queued", "processing", "error"]).length > 0,
      label: "Check duplicates for all files →",
      reason: "Save period choices for the whole batch and run duplicate checks together.",
    }
  }
  if (currentStep === 4) return reviewStageActionState()
  return { disabled: true, label: "", reason: "" }
}

function syncGlobalsFromActiveDoc() {
  const doc = getActiveDoc()
  if (!doc) {
    parsedData = null
    reviewRows = []
    importFilename = ""
    isPdfMode = false
    selectedParserId = null
    parserResults = []
    return
  }
  parsedData = doc.parsedData
  reviewRows = doc.reviewRows || []
  importFilename = doc.filename
  isPdfMode = !!doc.isPdfMode
  selectedParserId = doc.selectedParserId
  parserResults = doc.parserResults || []
}

function syncActiveDocFromGlobals() {
  const doc = getActiveDoc()
  if (!doc) return
  doc.parsedData = parsedData
  doc.reviewRows = reviewRows
  doc.isPdfMode = isPdfMode
  doc.selectedParserId = selectedParserId
  doc.parserResults = parserResults
}

function detectMonthYearFromRows(rows) {
  const counts = new Map()
  for (const row of rows || []) {
    const d = row.transaction_date
    if (!d) continue
    const s = typeof d === "string" ? d.slice(0, 10) : String(d)
    if (s.length < 10) continue
    const year = +s.slice(0, 4)
    const month = +s.slice(5, 7)
    if (!month || !year) continue
    const key = `${year}-${month}`
    counts.set(key, (counts.get(key) || 0) + 1)
  }
  if (!counts.size) return { month: 1, year: 2000 }

  let bestKey = null
  let bestCount = -1
  for (const [key, count] of counts) {
    if (count > bestCount) {
      bestCount = count
      bestKey = key
    }
  }
  const [year, month] = bestKey.split("-").map(Number)
  return { month, year }
}

function fpMonthOptionsHtml(selectedMonth) {
  return FP_MONTH_LABELS.map((label, i) => {
    const value = i + 1
    return `<option value="${value}"${value === selectedMonth ? " selected" : ""}>${label}</option>`
  }).join("")
}

function refreshKeywordStateForRow(row) {
  if (!row) return
  if (row.suggestion_source !== "keyword" && !(row.keyword_matches || []).length) return
  const analysis = CategoryKeywordTools.analyzeMerchantKeywordMatches(row.merchant_name, categories)
  row.normalized_merchant = analysis.normalizedMerchant
  row.keyword_matches = analysis.keywordMatches
  row.keyword_resolution_needed = analysis.keywordResolutionNeeded
  row.keyword_conflict_categories = analysis.keywordConflictCategories
  row.suggestion_source = analysis.keywordMatches.length ? "keyword" : "none"
  if (!row.category_name) {
    row.suggested_category = analysis.suggestedCategory || ""
  }
}

function refreshKeywordStateForRows(rows) {
  ;(rows || []).forEach((row) => refreshKeywordStateForRow(row))
}

function docRowCount(doc) {
  if (!doc) return 0
  const parserResult = getParserResultForDoc(doc)
  if (doc.parsedData && doc.parsedData.rows && doc.parsedData.rows.length) return doc.parsedData.rows.length
  if (doc.reviewRows && doc.reviewRows.length) return doc.reviewRows.length
  return ((parserResult && parserResult.rows) || []).length
}

function parserRowsForDoc(doc) {
  const result = getParserResultForDoc(doc)
  return (((result && result.rows) || [])).map((row) => ({ ...row, source_file: doc.filename, exclude: !!row.exclude }))
}

function getParserResultForDoc(doc) {
  if (!doc || !doc.parserResults || !doc.parserResults.length) return null
  return doc.parserResults.find((result) => result.parser_id === doc.selectedParserId) || doc.parserResults[0]
}

function getParserInsightsFor(results) {
  if (!results.length) {
    return { recommended: null, maxRows: 0 }
  }
  const recommended = results.reduce((best, current) => {
    const bestRows = (best.rows || []).length
    const currentRows = (current.rows || []).length
    if (currentRows !== bestRows) return currentRows > bestRows ? current : best
    return (current.skipped_rows || 0) < (best.skipped_rows || 0) ? current : best
  }, results[0])
  const maxRows = results.reduce((max, current) => Math.max(max, (current.rows || []).length), 0)
  return { recommended, maxRows }
}

function getParserInsights() {
  return getParserInsightsFor(parserResults || [])
}

function rowsClass(rowCount, maxRows) {
  if (!rowCount) return "empty"
  if (!maxRows || rowCount === maxRows) return "high"
  return rowCount / maxRows >= 0.6 ? "mid" : "low"
}

function formatParserSummary(result) {
  if (!result) return ""
  const rowCount = (result.rows || []).length
  const parts = [`${rowCount} row${rowCount !== 1 ? "s" : ""} found`]
  if (result.skipped_rows) parts.push(`${result.skipped_rows} skipped`)
  return parts.join(" · ")
}

function ensureSelectedParserRows(doc) {
  if (!doc) return
  const rows = parserRowsForDoc(doc)
  const currentPeriods = (doc.parsedData && doc.parsedData.perFilePeriod) || {}
  const my = detectMonthYearFromRows(rows)
  doc.parsedData = {
    format: doc.isPdfMode ? "pdf" : "generic",
    rows: rows.map((row) => ({ ...row })),
    errors: [],
    detected_month: my.month,
    detected_year: my.year,
    source_files: [doc.filename],
    perFilePeriod: currentPeriods,
  }
  doc.reviewRows = rows.map((row) => ({ ...row }))
  refreshKeywordStateForRows(doc.reviewRows)
}

function prepareDocForReview(doc) {
  if (!doc || doc.status !== "ready") return false
  if (doc.isPdfMode && !doc.periodReady) {
    ensureSelectedParserRows(doc)
    doc.periodReady = true
    if (doc.step < 3) doc.step = 3
  }
  if (!doc.reviewRows.length && doc.parsedData && doc.parsedData.rows && doc.parsedData.rows.length) {
    doc.reviewRows = doc.parsedData.rows.map((row) => ({ ...row }))
    refreshKeywordStateForRows(doc.reviewRows)
  }
  return !!(doc.parsedData && doc.parsedData.rows && doc.parsedData.rows.length)
}

function buildHistoryUrl(docId, step) {
  if (step === 5) return `${BASE_IMPORT_PATH}?step=done`
  if (!docId || step === 1) return BASE_IMPORT_PATH
  const params = new URLSearchParams({ doc: docId, step: STEP_NAMES[step] || STEP_NAMES[1] })
  return `${BASE_IMPORT_PATH}?${params.toString()}`
}

function updateHistory({ replace = false } = {}) {
  const url = buildHistoryUrl(activeDocId, currentStep)
  const state = { doc: activeDocId, step: currentStep }
  if (replace) {
    window.history.replaceState(state, "", url)
  } else {
    window.history.pushState(state, "", url)
  }
}

function renderStepIndicators(visibleStep) {
  ;[1, 2, 3, 4, 5].forEach((step) => {
    const stepEl = document.querySelector(`.step[data-step="${step}"]`)
    if (!stepEl) return
    stepEl.classList.remove("active", "done")
    if (step === visibleStep) stepEl.classList.add("active")
    else if (step < visibleStep) stepEl.classList.add("done")
  })
}

function renderDoneState() {
  document.getElementById("done-title").textContent = (doneSummary && doneSummary.title) || "Import complete"
  document.getElementById("done-summary").textContent = (doneSummary && doneSummary.summary) || ""
}

function previousStepFor(step) {
  if (step <= 2) return 1
  if (step === 3) return 2
  if (step === 4) return 3
  return 1
}

function stageToolbarMeta() {
  const doc = getActiveDoc()
  if (currentStep === 2) {
    if (!doc) {
      return {
        title: "Choose a parsing method",
        detail: "Pick a file in the queue to review its parsed rows.",
      }
    }
    if (doc.status === "processing") {
      const position = importDocs.findIndex((item) => item.id === doc.id) + 1
      return {
        title: `Processing ${doc.filename}`,
        detail: `File ${position} of ${importDocs.length}. You can go back to uploads while this finishes.`,
      }
    }
    if (doc.status === "queued") {
      const position = importDocs.findIndex((item) => item.id === doc.id) + 1
      return {
        title: `${doc.filename} is queued`,
        detail: `File ${position} of ${importDocs.length}. It will move into preview as soon as parsing finishes.`,
      }
    }
    if (doc.status === "error") {
      return {
        title: `${doc.filename} needs attention`,
        detail: doc.errorMessage || "Parsing failed.",
      }
    }
    if (doc.isPdfMode) {
      return {
        title: "Parser review",
        detail: doc.filename,
      }
    }
    return {
      title: "CSV preview",
      detail: doc.filename,
    }
  }

  if (currentStep === 3) {
    const readyDocs = getReadyDocs()
    return {
      title: "Confirm file periods",
      detail: readyDocs.length === 1
        ? readyDocs[0].filename
        : `${readyDocs.length} ready file${readyDocs.length !== 1 ? "s" : ""} in this batch`,
    }
  }

  if (currentStep === 4) {
    return {
      title: "Review rows",
      detail: importFilename
        ? `${importFilename} · ${reviewRows.length} row${reviewRows.length !== 1 ? "s" : ""}`
        : `${reviewRows.length} row${reviewRows.length !== 1 ? "s" : ""}`,
    }
  }

  return { title: "", detail: "" }
}

function renderStageToolbar() {
  const toolbar = document.getElementById("import-stage-toolbar")
  const titleEl = document.getElementById("import-stage-title")
  const detailEl = document.getElementById("import-stage-detail")
  const backBtn = document.getElementById("btn-stage-back")
  const selectAllBtn = document.getElementById("btn-select-all")
  const deselectAllBtn = document.getElementById("btn-deselect-all")
  const selectedCountEl = document.getElementById("review-selected-count")
  if (!toolbar || !titleEl || !detailEl || !backBtn || !selectAllBtn || !deselectAllBtn || !selectedCountEl) return

  const visible = currentStep >= 2 && currentStep <= 4 && (!!getActiveDoc() || !!importDocs.length)
  const reviewControlsVisible = visible && currentStep === 4
  toolbar.classList.toggle("hidden", !visible)
  selectAllBtn.classList.toggle("hidden", !reviewControlsVisible)
  deselectAllBtn.classList.toggle("hidden", !reviewControlsVisible)
  selectedCountEl.classList.toggle("hidden", !reviewControlsVisible)
  if (!visible) return

  const meta = stageToolbarMeta()
  titleEl.textContent = meta.title
  detailEl.textContent = meta.detail
  detailEl.classList.toggle("hidden", !meta.detail)
  backBtn.dataset.step = String(previousStepFor(currentStep))
}

function applyButtonState(button, state) {
  if (!button) return
  button.textContent = state.label
  button.dataset.defaultLabel = state.label
  button.disabled = !!state.disabled
  if (state.reason) button.title = state.reason
  else button.removeAttribute("title")
}

function renderStageActionButtons() {
  const primaryBtn = document.getElementById("btn-stage-primary")
  if (!primaryBtn) return
  const visible = currentStep >= 2 && currentStep <= 4 && (!!getActiveDoc() || !!importDocs.length)
  primaryBtn.classList.toggle("hidden", !visible)
  if (!visible) return
  applyButtonState(primaryBtn, queuePrimaryActionState())
}

function queueStatusText(doc) {
  if (doc.status === "processing") return "Processing"
  if (doc.status === "queued") return "Queued"
  if (doc.status === "error") return "Needs attention"
  if (currentStep === 2) return "Ready"
  if (currentStep === 3) return "Confirm period"
  if (currentStep === 4) return doc.reviewReady ? "Ready to import" : "Needs review"
  return "Ready"
}

function renderImportQueue() {
  const card = document.getElementById("import-queue-card")
  if (!card) return
  if (!importDocs.length) {
    card.classList.add("hidden")
    return
  }
  card.classList.remove("hidden")

  const ready = getReadyDocs().length
  const loading = importDocs.filter((doc) => doc.status === "queued" || doc.status === "processing").length
  const errors = importDocs.filter((doc) => doc.status === "error").length
  const parts = [`${importDocs.length} file${importDocs.length !== 1 ? "s" : ""} in this batch`]
  if (ready) parts.push(`${ready} ready`)
  if (loading) parts.push(`${loading} loading`)
  if (errors) parts.push(`${errors} need attention`)
  const summary = document.getElementById("import-queue-summary")
  if (summary) summary.textContent = parts.join(" · ")

  const tabs = document.getElementById("import-doc-tabs")
  if (!tabs) return
  tabs.innerHTML = ""

  importDocs.forEach((doc) => {
    const wrapper = document.createElement("div")
    wrapper.className = `import-doc-tab state-${doc.status}${doc.id === activeDocId && currentStep !== 5 ? " active" : ""}`

    const openBtn = document.createElement("button")
    openBtn.type = "button"
    openBtn.className = "import-doc-open"
    const rowCount = docRowCount(doc)
    const statusText = queueStatusText(doc)
    const statusClass =
      doc.status === "ready" ? "ready"
      : doc.status === "error" ? "error"
      : "processing"
    openBtn.innerHTML = `
      <span class="import-doc-name" title="${escHtml(doc.filename)}">${escHtml(doc.filename)}</span>
      <span class="import-doc-meta">
        <span class="import-doc-status ${statusClass}">${escHtml(statusText)}</span>
        ${rowCount ? `<span class="import-doc-count">${rowCount} row${rowCount !== 1 ? "s" : ""}</span>` : ""}
      </span>
    `
    openBtn.addEventListener("click", () => {
      activateDoc(doc.id, { step: currentStep, pushHistory: true })
    })

    const removeBtn = document.createElement("button")
    removeBtn.type = "button"
    removeBtn.className = "import-doc-remove"
    removeBtn.setAttribute("aria-label", `Remove ${doc.filename} from this batch`)
    removeBtn.textContent = "×"
    removeBtn.addEventListener("click", () => removeImportDoc(doc.id))

    wrapper.appendChild(openBtn)
    wrapper.appendChild(removeBtn)
    tabs.appendChild(wrapper)
  })
}

function updateParseStageIntro() {
  const title = document.getElementById("parser-step-title")
  const copy = document.getElementById("parser-step-copy")
  const doc = getActiveDoc()
  if (!title || !copy || !doc) return
  if (doc.isPdfMode) {
    title.textContent = "Choose a parsing method"
    copy.textContent = "All files stay in Parse until you move the whole batch forward. Start with the option that found the most rows, then compare skipped rows, warnings, and the preview."
    return
  }
  title.textContent = "CSV parsed successfully"
  copy.textContent = "CSV files do not need a parser choice. Review the preview here, then move the whole batch to File periods when every file looks good."
}

function renderProcessingPanel() {
  const panel = document.getElementById("import-processing-panel")
  const body = document.getElementById("import-processing-body")
  const doc = getActiveDoc()
  if (!panel || !body) return
  if (!doc || currentStep !== 2 || !["queued", "processing", "error"].includes(doc.status)) {
    panel.classList.add("hidden")
    body.innerHTML = ""
    return
  }

  panel.classList.remove("hidden")
  if (doc.status === "error") {
    panel.classList.add("error-state")
    body.innerHTML = `
      <div class="import-processing-title">This file needs attention</div>
      <div class="import-processing-file">${escHtml(doc.filename)}</div>
      <div class="import-processing-copy">${escHtml(doc.errorMessage || "Parsing failed.")}</div>
      <div class="import-processing-actions">
        <button type="button" class="btn btn-secondary" id="btn-processing-back">Back to uploads</button>
        <button type="button" class="btn btn-ghost" id="btn-processing-remove">Remove file</button>
      </div>
    `
    const backBtn = body.querySelector("#btn-processing-back")
    const removeBtn = body.querySelector("#btn-processing-remove")
    if (backBtn) backBtn.addEventListener("click", () => goStep(1))
    if (removeBtn) removeBtn.addEventListener("click", () => removeImportDoc(doc.id))
    return
  }

  panel.classList.remove("error-state")
  const position = importDocs.findIndex((item) => item.id === doc.id) + 1
  const total = importDocs.length
  const title = doc.status === "processing" ? "Processing your file" : "Waiting in the queue"
  const copy =
    doc.status === "processing"
      ? "Large PDFs and image-heavy statements can take a bit. You can go back to uploads while we keep working in the background."
      : "This file is next in line. As soon as it is ready, you can switch into it without losing anything from the rest of the batch."
  body.innerHTML = `
    <div class="import-processing-spinner"></div>
    <div class="import-processing-title">${title}</div>
    <div class="import-processing-file">${escHtml(doc.filename)}</div>
    <div class="import-processing-progress">File ${position} of ${total}</div>
    <div class="import-processing-copy">${copy}</div>
    <div class="import-processing-actions">
      <button type="button" class="btn btn-secondary" id="btn-processing-back">Back to uploads</button>
      <button type="button" class="btn btn-ghost" id="btn-processing-remove">Remove file</button>
    </div>
  `
  const backBtn = body.querySelector("#btn-processing-back")
  const removeBtn = body.querySelector("#btn-processing-remove")
  if (backBtn) backBtn.addEventListener("click", () => goStep(1))
  if (removeBtn) removeBtn.addEventListener("click", () => removeImportDoc(doc.id))
}

function renderStepPanels() {
  let visibleStep = currentStep
  if (visibleStep !== 5 && !getActiveDoc()) visibleStep = 1

  ;[1, 2, 3, 4, 5].forEach((step) => {
    const el = document.getElementById(`step-${step}`)
    if (el) el.classList.toggle("hidden", step !== visibleStep)
  })

  const parserStepContent = document.getElementById("parser-step-content")
  const activeDoc = getActiveDoc()
  const showProcessing = visibleStep === 2 && activeDoc && ["queued", "processing", "error"].includes(activeDoc.status)
  if (parserStepContent) {
    parserStepContent.classList.toggle(
      "hidden",
      visibleStep !== 2 || showProcessing || !activeDoc || activeDoc.status !== "ready"
    )
  }

  if (visibleStep === 2) {
    renderProcessingPanel()
    if (!showProcessing && activeDoc && activeDoc.status === "ready") {
      updateParseStageIntro()
      renderParserTabs()
    }
  } else {
    renderProcessingPanel()
  }

  if (visibleStep === 3) {
    renderFilePeriodPickers()
  }
  if (visibleStep === 4) {
    renderReviewTable()
    renderReviewUnknownCatsBanner()
  }
  if (visibleStep === 5) {
    renderDoneState()
  }

  renderStepIndicators(visibleStep)
}

function renderApp() {
  syncGlobalsFromActiveDoc()
  renderImportQueue()
  renderStepPanels()
  renderStageToolbar()
  renderStageActionButtons()
}

function goStep(step, options = {}) {
  syncActiveDocFromGlobals()
  const nextStep = clampBatchStep(step)
  currentStep = nextStep
  renderApp()
  if (options.pushHistory !== false) {
    updateHistory({ replace: !!options.replaceHistory })
  }
  markDraftDirty()
}

function activateDoc(docId, options = {}) {
  if (activeDocId !== docId) syncActiveDocFromGlobals()
  const doc = getDocById(docId)
  if (!doc) {
    activeDocId = null
    currentStep = clampBatchStep(doneSummary ? 5 : 1)
    renderApp()
    if (options.pushHistory !== false) {
      updateHistory({ replace: !!options.replaceHistory })
    }
    markDraftDirty()
    return
  }
  activeDocId = doc.id
  syncGlobalsFromActiveDoc()
  const nextStep = clampBatchStep(options.step || currentStep || 1)
  currentStep = nextStep
  renderApp()
  if (options.pushHistory !== false) {
    updateHistory({ replace: !!options.replaceHistory })
  }
  markDraftDirty()
}

function focusBestRemainingDoc({ replaceHistory = true } = {}) {
  if (!importDocs.length) {
    activeDocId = null
    if (doneSummary) {
      goStep(5, { replaceHistory, pushHistory: true })
    } else {
      goStep(1, { replaceHistory, pushHistory: true })
    }
    return
  }
  const nextDoc =
    importDocs.find((doc) => doc.status === "ready") ||
    importDocs.find((doc) => doc.status === "processing" || doc.status === "queued") ||
    importDocs[0]
  activateDoc(nextDoc.id, { step: clampBatchStep(currentStep || 1), replaceHistory, pushHistory: true })
}

function removeImportDoc(docId) {
  syncActiveDocFromGlobals()
  const index = importDocs.findIndex((doc) => doc.id === docId)
  if (index < 0) return
  const wasActive = activeDocId === docId
  const wasOnUpload = currentStep === 1
  importDocs.splice(index, 1)
  void deleteDraftFiles([docId])
  if (doneSummary && importDocs.length) doneSummary = null
  if (!wasActive) {
    renderApp()
    scheduleDraftSave()
    return
  }
  if (wasOnUpload) {
    activeDocId = importDocs[0] ? importDocs[0].id : null
    currentStep = 1
    renderApp()
    updateHistory({ replace: true })
    scheduleDraftSave()
    return
  }
  focusBestRemainingDoc({ replaceHistory: true })
  scheduleDraftSave()
}

function initializeHistory() {
  const step = clampBatchStep(activeDocId ? currentStep : (doneSummary ? 5 : 1))
  currentStep = step
  window.history.replaceState({ doc: activeDocId, step }, "", buildHistoryUrl(activeDocId, step))
  window.addEventListener("popstate", () => {
    const params = new URL(window.location.href).searchParams
    const stepName = params.get("step")
    if (stepName === "done" && doneSummary && !importDocs.length) {
      activeDocId = null
      currentStep = 5
      renderApp()
      return
    }

    const docId = params.get("doc")
    const step = STEP_FROM_NAME[stepName] || 1
    if (!docId || !getDocById(docId)) {
      currentStep = 1
      renderApp()
      return
    }
    activeDocId = docId
    currentStep = clampBatchStep(step)
    renderApp()
  })
}

function shouldAutoOpenDoc(docId) {
  const activeDoc = getActiveDoc()
  if (!activeDoc) return true
  if (activeDoc.id === docId) return true
  if (currentStep === 1) return true
  return false
}

async function parseStructuredDoc(doc) {
  await ensureDocFileLoaded(doc)
  const fd = new FormData()
  fd.append("file", doc.file)
  const resp = await fetch("/api/import/parse-all", { method: "POST", body: fd })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || resp.statusText)
  }
  const results = await resp.json()
  if (!results.length) {
    throw new Error("No parsers returned results.")
  }
  const { recommended, maxRows } = getParserInsightsFor(results)
  if (maxRows === 0) {
    throw new Error("No rows could be extracted from this file. It may be a scanned/image PDF that requires OCR, or an unsupported format.")
  }
  doc.parserResults = results
  doc.selectedParserId = (recommended || results[0]).parser_id
  ensureSelectedParserRows(doc)
  doc.periodReady = false
  doc.reviewReady = false
  doc.step = 2
}

async function parseCsvDoc(doc) {
  await ensureDocFileLoaded(doc)
  const parsed = await API.parseCSV(doc.file)
  if (!parsed.format) {
    throw new Error(((parsed.errors || [])[0]) || "Unrecognized CSV format.")
  }
  const rows = (parsed.rows || []).map((row) => ({ ...row, source_file: doc.filename, exclude: !!row.exclude }))
  if (!rows.length) {
    throw new Error("No rows could be parsed from this file.")
  }
  const my = detectMonthYearFromRows(rows)
  doc.parsedData = {
    ...parsed,
    rows: rows.map((row) => ({ ...row })),
    detected_month: my.month,
    detected_year: my.year,
    source_files: [doc.filename],
    perFilePeriod: {},
  }
  doc.reviewRows = rows.map((row) => ({ ...row }))
  refreshKeywordStateForRows(doc.reviewRows)
  doc.parserResults = []
  doc.selectedParserId = null
  doc.periodReady = true
  doc.reviewReady = false
  doc.step = 3
  if (parsed.errors && parsed.errors.length) {
    showAlert(
      alertsEl,
      parsed.errors.slice(0, 6).map((err) => `${doc.filename}: ${err}`).join("\n") + (parsed.errors.length > 6 ? "\n…" : ""),
      "warning"
    )
  }
}

async function processQueue() {
  if (queueProcessing) return
  queueProcessing = true
  try {
    while (true) {
      const doc = importDocs.find((item) => item.status === "queued")
      if (!doc) break
      doc.status = "processing"
      doc.errorMessage = ""
      renderApp()
      scheduleDraftSave()
      if (activeDocId === doc.id && currentStep !== 1) {
        updateHistory({ replace: true })
      }
      await yieldToBrowser()

      try {
        if (doc.isPdfMode) await parseStructuredDoc(doc)
        else await parseCsvDoc(doc)
        if (!getDocById(doc.id)) continue
        doc.status = "ready"
        doc.file = null
        scheduleDraftSave()
        if (shouldAutoOpenDoc(doc.id)) {
          activateDoc(doc.id, {
            step: currentStep === 1 ? 2 : currentStep,
            replaceHistory: currentStep > 1,
            pushHistory: true,
          })
        } else {
          renderApp()
        }
      } catch (error) {
        if (!getDocById(doc.id)) continue
        doc.status = "error"
        doc.file = null
        doc.errorMessage = error.message || "Parse failed."
        showAlert(alertsEl, `${doc.filename}: ${doc.errorMessage}`, "error")
        scheduleDraftSave()
        if (shouldAutoOpenDoc(doc.id)) {
          activateDoc(doc.id, {
            step: 2,
            replaceHistory: currentStep !== 1,
            pushHistory: true,
          })
        } else {
          renderApp()
        }
      }
      await yieldToBrowser()
    }
  } finally {
    queueProcessing = false
    renderApp()
    scheduleDraftSave()
  }
  // Safety: docs may have been added while we were finishing the last item
  if (importDocs.some((d) => d.status === "queued")) {
    void processQueue()
  }
}

async function handleFileList(fileList) {
  const files = [...fileList].filter(isSupportedImportFile)
  if (!files.length) {
    showAlert(alertsEl, "Choose .csv, .pdf, .ofx, or .qfx files.", "error")
    return
  }
  fileInput.value = ""
  doneSummary = null

  const firstDocId = importDocs[0] ? importDocs[0].id : null
  const newDocs = files.map((file) => createImportDoc(file))
  await persistDraftFiles(newDocs)
  importDocs.push(...newDocs)
  scheduleDraftSave()

  activeDocId = newDocs[0].id
  currentStep = 2
  renderApp()
  updateHistory({ replace: !firstDocId })

  void processQueue()
}

function syncPerFilePeriodFromPickers(doc = getActiveDoc()) {
  if (!doc || !doc.parsedData || !doc.parsedData.source_files) return
  const data = doc.parsedData
  if (!data.perFilePeriod) data.perFilePeriod = {}
  document.querySelectorAll(`#file-periods .fp-row[data-doc-id="${doc.id}"]`).forEach((el) => {
    const idx = +el.dataset.fpIdx
    const fname = data.source_files[idx]
    if (!fname) return
    const monthEl = el.querySelector(".fp-month")
    const yearEl = el.querySelector(".fp-year")
    if (!monthEl || !yearEl) return
    data.perFilePeriod[fname] = { month: +monthEl.value, year: +yearEl.value }
  })
}

function applyImportPeriodsToRows(rows, doc = getActiveDoc()) {
  if (!rows || !doc || !doc.parsedData) return
  syncPerFilePeriodFromPickers(doc)
  const data = doc.parsedData
  const sourceFiles = data.source_files || []
  const map = data.perFilePeriod || {}
  const defaultMonth = data.detected_month || 1
  const defaultYear = data.detected_year || 2000
  rows.forEach((row) => {
    const filename = row.source_file || sourceFiles[0] || ""
    const period = map[filename]
    if (period && period.month >= 1 && period.month <= 12 && period.year >= 2000 && period.year <= 2100) {
      row.import_month = period.month
      row.import_year = period.year
    } else {
      row.import_month = defaultMonth
      row.import_year = defaultYear
    }
  })
}

function renderFilePeriodPickers() {
  const host = document.getElementById("file-periods")
  if (!host) return

  const readyDocs = importDocs.filter((d) => d.status === "ready" && d.parsedData && d.parsedData.source_files && d.parsedData.source_files.length)
  host.innerHTML = ""
  if (!readyDocs.length) {
    return
  }

  // Column header row
  const header = document.createElement("div")
  header.className = "file-period-header"
  header.innerHTML = `
    <span class="file-period-header-label">File</span>
    <span class="file-period-header-label">Month</span>
    <span class="file-period-header-label">Year</span>
  `
  host.appendChild(header)

  readyDocs.forEach((doc) => {
    const data = doc.parsedData
    if (!data.perFilePeriod) data.perFilePeriod = {}

    data.source_files.forEach((fname, idx) => {
      const subRows = data.rows.filter((row) => row.source_file === fname)
      const detected = detectMonthYearFromRows(subRows.length ? subRows : data.rows)
      const saved = data.perFilePeriod[fname] || detected
      data.perFilePeriod[fname] = { month: saved.month, year: saved.year }

      const row = document.createElement("div")
      row.className = "file-period-row"
      row.dataset.fpIdx = String(idx)
      row.dataset.docId = doc.id
      row.innerHTML = `
        <div class="file-period-file" title="${escHtml(fname)}">${escHtml(fname)}</div>
        <select class="fp-month file-period-control">
          ${fpMonthOptionsHtml(saved.month)}
        </select>
        <input type="number" class="fp-year file-period-control" min="2000" max="2100" value="${saved.year}" />
      `
      const onChange = () => {
        syncPerFilePeriodFromPickers(doc)
        markDraftDirty()
      }
      const monthSelect = row.querySelector(".fp-month")
      const yearInput = row.querySelector(".fp-year")
      if (monthSelect) monthSelect.addEventListener("change", onChange)
      if (yearInput) {
        yearInput.addEventListener("change", onChange)
        yearInput.addEventListener("input", onChange)
      }
      host.appendChild(row)
    })
  })
}

function rowsPayloadForDuplicateCheck(rows) {
  return rows.map((row) => {
    const out = { ...row }
    delete out.duplicate
    delete out.duplicate_in_import
    delete out.duplicate_in_database
    return out
  })
}

function mapDuplicateCheckResult(resultRows, previousRows) {
  return resultRows.map((row, i) => {
    const duplicate = !!row.duplicate
    const previousRow = previousRows[i]
    let exclude
    if (duplicate) {
      exclude = previousRow && previousRow.duplicate ? !!previousRow.exclude : true
    } else {
      exclude = !!row.exclude
    }
    return {
      ...row,
      duplicate,
      exclude,
      duplicate_in_import: !!row.duplicate_in_import,
      duplicate_in_database: !!row.duplicate_in_database,
    }
  })
}

function applyDuplicateCheckResult(resultRows, previousRows) {
  reviewRows = mapDuplicateCheckResult(resultRows, previousRows)
  refreshKeywordStateForRows(reviewRows)
}

function duplicateCheckDocs() {
  return importDocs.filter((doc) => doc.status === "ready").filter((doc) => prepareDocForReview(doc))
}

async function refreshDuplicatesAcrossDocs() {
  const docs = duplicateCheckDocs()
  if (!docs.length) return
  categories = await API.getCategories()
  const previous = new Map(docs.map((doc) => [doc.id, doc.reviewRows.map((row) => ({ ...row }))]))
  const counts = []
  const payload = []

  docs.forEach((doc) => {
    const rows = doc.reviewRows.map((row) => ({ ...row }))
    applyImportPeriodsToRows(rows, doc)
    counts.push({ docId: doc.id, count: rows.length })
    payload.push(...rowsPayloadForDuplicateCheck(rows))
  })

  const result = await API.checkDuplicates(payload)
  let offset = 0
  counts.forEach(({ docId, count }) => {
    const doc = getDocById(docId)
    if (!doc) {
      offset += count
      return
    }
    const slice = result.rows.slice(offset, offset + count)
    offset += count
    doc.reviewRows = mapDuplicateCheckResult(slice, previous.get(docId) || [])
    refreshKeywordStateForRows(doc.reviewRows)
    doc.reviewReady = true
  })
  syncGlobalsFromActiveDoc()
  markDraftDirty()
}

async function runDuplicateCheckAndGoReview() {
  const doc = getActiveDoc()
  if (!doc) return
  syncPerFilePeriodFromPickers(doc)
  await refreshDuplicatesAcrossDocs()
  if (!getActiveDoc()) return
  goStep(4)
}

function rowMissingRequired(row) {
  const missing = []
  if (!row.transaction_date) missing.push("date")
  if (!row.merchant_name || !String(row.merchant_name).trim()) missing.push("merchant")
  if (row.amount === null || row.amount === undefined || isNaN(Number(row.amount))) missing.push("amount")
  const validTypes = ["expense", "income", "refund", "transfer"]
  if (!row.transaction_type || !validTypes.includes(row.transaction_type)) missing.push("type")
  return missing
}

function refreshDupHintForRow(idx) {
  const el = document.querySelector(`[data-dup-hint="${idx}"]`)
  if (!el) return
  const row = reviewRows[idx]
  if (!row || !row.duplicate) return
  el.textContent = row.exclude ? "deselected" : "will import"
}

function renderReviewUnknownCatsBanner() {
  const banner = document.getElementById("review-unknown-cats-banner")
  if (!banner) return
  if (!isPdfMode) {
    banner.classList.add("hidden")
    return
  }
  const result = parserResults.find((parser) => parser.parser_id === selectedParserId)
  const cats = (result && result.unknown_pdf_categories) || []
  if (!cats.length) {
    banner.classList.add("hidden")
    return
  }
  const pills = cats.map((cat) => `<span class="unknown-cats-pill">${escHtml(cat)}</span>`).join("")
  banner.innerHTML = `
    <div class="unknown-cats-title">PDF categories not yet resolved</div>
    <p class="text-muted unknown-cats-copy">These categories from your PDF were not matched. Go back to Parser step to decide, or they will import as <em>uncategorized</em>.</p>
    <div class="unknown-cats-pills">${pills}</div>`
  banner.classList.remove("hidden")
}

function reviewCategoryLabel(row) {
  return row.category_name || row.suggested_category || "Choose category"
}

function reviewCategoryButtonHtml(row, idx, tabIndex) {
  return `
    <button
      type="button"
      class="review-inp category-picker-trigger cat-pick-btn"
      data-idx="${idx}"
      tabindex="${tabIndex}"
      title="Choose category"
    >
      <span class="category-picker-trigger-label">${escHtml(reviewCategoryLabel(row))}</span>
      <span class="category-picker-trigger-caret" aria-hidden="true">▾</span>
    </button>
  `
}

function renderReviewTable(previewMode = false) {
  const tbodyId = previewMode ? "parser-preview-tbody" : "review-tbody"
  const tbody = document.getElementById(tbodyId)
  if (!tbody) return
  tbody.innerHTML = ""

  const duplicateCount = reviewRows.filter((row) => row.duplicate).length
  const duplicateExcluded = reviewRows.filter((row) => row.duplicate && row.exclude).length
  const duplicateIncluded = reviewRows.filter((row) => row.duplicate && !row.exclude).length
  const duplicateInUpload = reviewRows.filter((row) => row.duplicate && row.duplicate_in_import).length
  const duplicateInDbOnly = reviewRows.filter((row) => row.duplicate && row.duplicate_in_database && !row.duplicate_in_import).length
  const paymentCount = reviewRows.filter((row) => row.is_payment).length
  const keywordCount = reviewRows.filter((row) => row.keyword_resolution_needed).length
  const duplicateIndexes = reviewRows.map((row, i) => (row.duplicate ? i + 1 : null)).filter((n) => n != null)
  const showFileCol = !previewMode && !!(parsedData && parsedData.source_files && parsedData.source_files.length > 1)

  if (!previewMode) {
    const thSource = document.getElementById("th-source")
    if (thSource) thSource.classList.toggle("hidden", !showFileCol)
  }

  if (!previewMode) {
    const dupBanner = document.getElementById("review-dup-banner")
    const dupBannerText = document.getElementById("review-dup-banner-text")
    if (duplicateCount) {
      dupBanner.classList.remove("hidden")
      const list = duplicateIndexes.length <= 15
        ? duplicateIndexes.join(", ")
        : `${duplicateIndexes.slice(0, 15).join(", ")}, …`
      const parts = [`Rows ${list} match an earlier row in this upload or a saved transaction.`]
      if (duplicateInUpload) parts.push(`${duplicateInUpload} also repeat another row in this upload.`)
      if (duplicateInDbOnly) parts.push(`${duplicateInDbOnly} already exist in your database.`)
      parts.push("Same reference on a different date still counts as new. Duplicates start unchecked.")
      dupBannerText.textContent = parts.join(" ")
    } else {
      dupBanner.classList.add("hidden")
    }

    const keywordBanner = document.getElementById("review-keyword-banner")
    const keywordBannerText = document.getElementById("review-keyword-banner-text")
    if (keywordCount) {
      keywordBanner.classList.remove("hidden")
      keywordBannerText.textContent =
        `${keywordCount} row(s) matched keywords from more than one category. ` +
        `Pick the right category and remove saved keywords if needed. ` +
        `Same-category matches are handled automatically.`
    } else {
      keywordBanner.classList.add("hidden")
    }
  }

  let tabIdx = 1
  reviewRows.forEach((row, i) => {
    const tr = document.createElement("tr")
    if (row.duplicate) tr.classList.add("review-dup")
    if (row.exclude) tr.classList.add("review-excluded")

    const checked = !row.exclude ? "checked" : ""
    let dupHint = ""
    if (row.duplicate) {
      if (row.duplicate_in_import && row.duplicate_in_database) dupHint = "upload+db"
      else if (row.duplicate_in_import) dupHint = "in upload"
      else if (row.duplicate_in_database) dupHint = "in database"
    }
    const dupBadge = row.duplicate
      ? `<span class="badge badge-dup">DUP</span><span class="text-muted dup-badge-hint">${dupHint ? escHtml(dupHint) : ""}</span>`
      : ""
    const payBadge = row.is_payment ? `<span class="badge badge-transfer">PMT</span>` : ""
    const kwBadge = row.keyword_resolution_needed
      ? `<button type="button" class="btn btn-ghost btn-sm kw-review-btn" data-idx="${i}">Resolve</button>`
      : ""

    const typeOptions = ["expense", "income", "refund", "transfer"].map((type) =>
      `<option value="${type}" ${row.transaction_type === type ? "selected" : ""}>${type.charAt(0).toUpperCase() + type.slice(1)}</option>`
    ).join("")

    const tabIndex = {
      chk: tabIdx++,
      date: tabIdx++,
      merchant: tabIdx++,
      amount: tabIdx++,
      type: tabIdx++,
      cat: tabIdx++,
      notes: tabIdx++,
    }

    const dupChkAttrs = row.duplicate
      ? `tabindex="${tabIndex.chk}" title="Duplicate: unchecked by default; check to include in import"`
      : `tabindex="${tabIndex.chk}"`
    const sourceCell = showFileCol
      ? `<td class="text-muted source-file-cell" title="${escHtml(row.source_file || "")}">${escHtml((row.source_file || "—").slice(0, 22))}${(row.source_file || "").length > 22 ? "…" : ""}</td>`
      : ""

    const missingFields = rowMissingRequired(row)
    const missingDate = missingFields.includes("date")
    const missingMerchant = missingFields.includes("merchant")
    const missingAmount = missingFields.includes("amount")
    const missingType = missingFields.includes("type")

    const statusCell = previewMode
      ? `<td style="white-space:nowrap">${payBadge}${missingFields.length ? `<span class="badge badge-missing" title="Missing: ${missingFields.join(", ")}">!</span>` : ""}</td>`
      : `<td style="white-space:nowrap">
          ${dupBadge}${payBadge}${kwBadge}
          ${row.duplicate ? `<span class="text-muted dup-import-hint" data-dup-hint="${i}">${row.exclude ? "deselected" : "will import"}</span>` : ""}
         </td>`

    tr.innerHTML = `
      <td style="padding-left:0.75rem">
        <input type="checkbox" class="row-chk" data-idx="${i}" ${checked} ${dupChkAttrs} />
      </td>
      <td class="text-muted row-index-cell">${i + 1}</td>
      ${sourceCell}
      <td>
        <input type="date" class="review-inp date-inp${missingDate ? " required-missing" : ""}" data-idx="${i}"
          value="${row.transaction_date || ""}" tabindex="${tabIndex.date}" />
      </td>
      <td>
        <input type="text" class="review-inp merchant-inp${missingMerchant ? " required-missing" : ""}" data-idx="${i}"
          value="${escHtml(row.merchant_name || "")}" placeholder="merchant…" tabindex="${tabIndex.merchant}" />
      </td>
      <td>
        <input type="number" class="review-inp review-amount-inp amount-inp${missingAmount ? " required-missing" : ""}" data-idx="${i}"
          value="${row.amount != null ? row.amount : ""}" step="0.01" min="0" tabindex="${tabIndex.amount}" />
      </td>
      <td>
        <select class="review-inp type-sel${missingType ? " required-missing" : ""}" data-idx="${i}" tabindex="${tabIndex.type}">${typeOptions}</select>
      </td>
      <td>
        ${reviewCategoryButtonHtml(row, i, tabIndex.cat)}
      </td>
      <td>
        <input type="text" class="review-inp notes-inp" data-idx="${i}"
          placeholder="notes…" value="${escHtml(row.notes || "")}" tabindex="${tabIndex.notes}" />
      </td>
      ${statusCell}
    `
    tbody.appendChild(tr)
  })

  attachReviewListeners()
  updateSelectedCount()
  if (!previewMode) renderStageToolbar()
}

function renderParserPreviewTable() {
  const tbody = document.getElementById("parser-preview-tbody")
  const label = document.getElementById("parser-preview-label")
  if (!tbody) return
  tbody.innerHTML = ""

  const result = parserResults.find((parser) => parser.parser_id === selectedParserId)
  const rows = isPdfMode ? ((result && result.rows) || []) : (((parsedData && parsedData.rows) || []))
  if (label) {
    if (isPdfMode && result) label.textContent = formatParserSummary(result)
    else label.textContent = `${rows.length} row${rows.length !== 1 ? "s" : ""} found`
  }

  rows.forEach((row, i) => {
    const missing = rowMissingRequired(row)
    const tr = document.createElement("tr")
    const categoryDisplay = row.category_name || row.suggested_category || ""
    const missingHint = missing.length
      ? `<span class="badge badge-missing" title="Missing: ${missing.join(", ")}" style="margin-left:0.3rem">!</span>`
      : ""
    tr.innerHTML = `
      <td class="text-muted row-index-cell">${i + 1}</td>
      <td>${escHtml(String(row.transaction_date || "—"))}</td>
      <td>${escHtml(row.merchant_name || "—")}${missingHint}</td>
      <td>${row.amount != null ? row.amount : "—"}</td>
      <td>${escHtml(row.transaction_type || "—")}</td>
      <td class="text-muted preview-category-cell">${escHtml(categoryDisplay || "uncategorized")}</td>
    `
    tbody.appendChild(tr)
  })
}

function renderParserWarnings() {
  const banner = document.getElementById("parser-warnings")
  if (!banner) return
  if (!isPdfMode) {
    banner.classList.add("hidden")
    return
  }
  const result = parserResults.find((parser) => parser.parser_id === selectedParserId)
  if (!result || (!result.warnings.length && !result.errors.length)) {
    banner.classList.add("hidden")
    return
  }
  const warningItems = result.warnings.map((warning) => `<li>${escHtml(warning)}</li>`).join("")
  const errorItems = result.errors.map((error) => `<li>${escHtml(error)}</li>`).join("")
  banner.innerHTML = `
    <div class="parser-warning-title">Why this might not be perfect</div>
    ${warningItems ? `<ul class="parser-warning-list">${warningItems}</ul>` : ""}
    ${errorItems ? `<ul class="parser-warning-list parser-error-list">${errorItems}</ul>` : ""}`
  banner.classList.remove("hidden")
}

function buildUnknownCatRows(cats) {
  return cats.map((cat) => `
    <label class="unknown-cat-choice">
      <input type="checkbox" class="unknown-cat-cb" data-cat="${escHtml(cat)}" checked>
      <span class="unknown-cats-pill">${escHtml(cat)}</span>
    </label>`).join("")
}

function renderUnknownCatsBannerStep2() {
  const banner = document.getElementById("parser-unknown-cats")
  if (!banner) return
  if (!isPdfMode) {
    banner.classList.add("hidden")
    return
  }
  const result = parserResults.find((parser) => parser.parser_id === selectedParserId)
  const cats = (result && result.unknown_pdf_categories) || []
  if (!cats.length) {
    banner.classList.add("hidden")
    return
  }
  banner.innerHTML = `
    <div class="unknown-cats-title">Categories from PDF not in your system</div>
    <p class="text-muted unknown-cats-copy">These categories from the file don't match any in your system. <strong style="color:var(--tone-warning-text)">Optional</strong> — if you skip this, all unrecognized categories will fall back to keyword matching automatically.</p>
    <div id="unknown-cats-list" style="margin:0.5rem 0 0.75rem">${buildUnknownCatRows(cats)}</div>
    <div class="unknown-cats-actions">
      <button class="btn btn-ghost btn-sm" onclick="handleUnknownCatsSelectAll(true)">Select all</button>
      <button class="btn btn-ghost btn-sm" onclick="handleUnknownCatsSelectAll(false)">Clear all</button>
      <button class="btn btn-ghost btn-sm" onclick="handleUnknownCatsAction('create')" style="margin-left:auto">Add to categories</button>
      <button class="btn btn-ghost btn-sm" onclick="handleUnknownCatsAction('autosort')">Use existing categories</button>
    </div>`
  banner.classList.remove("hidden")
}

function renderParserTabs() {
  const container = document.getElementById("parser-tabs")
  if (!container) return
  container.innerHTML = ""
  if (!isPdfMode) {
    const rows = ((parsedData && parsedData.rows) || [])
    const tab = document.createElement("div")
    tab.className = `parser-tab rows-${rows.length ? "high" : "empty"} active`
    tab.innerHTML = `
      <div class="parser-tab-top">
        <div class="parser-tab-name">CSV Import</div>
        <div class="parser-tab-tags">
          <span class="parser-pill parser-pill-rows">No parser needed</span>
        </div>
      </div>
      <div class="parser-row-count ${rows.length ? "high" : "empty"}">${rows.length ? `${rows.length} row${rows.length !== 1 ? "s" : ""} found` : "No rows found"}</div>
      <div class="parser-tab-meta"></div>`
    container.appendChild(tab)
    refreshParserPanel()
    return
  }
  const insights = getParserInsights()
  parserResults.forEach((result) => {
    const isActive = result.parser_id === selectedParserId
    const rowCount = (result.rows || []).length
    const rowTone = rowsClass(rowCount, insights.maxRows)
    const isMostRows = insights.maxRows > 0 && rowCount === insights.maxRows
    const tab = document.createElement("div")
    tab.className = `parser-tab rows-${rowTone}${isActive ? " active" : ""}`
    tab.dataset.parserId = result.parser_id
    tab.innerHTML = `
      <div class="parser-tab-top">
        <div class="parser-tab-name">${escHtml(result.parser_label)}</div>
        <div class="parser-tab-tags">
          ${isMostRows ? '<span class="parser-pill parser-pill-rows">Most rows</span>' : ""}
        </div>
      </div>
      <div class="parser-row-count ${rowTone}${rowCount ? "" : " empty"}">${rowCount ? `${rowCount} row${rowCount !== 1 ? "s" : ""} found` : "No rows found"}</div>
      <div class="parser-tab-meta">
        ${result.skipped_rows ? `<span class="parser-meta-danger">${result.skipped_rows} skipped</span>` : ""}
      </div>`
    tab.addEventListener("click", () => selectParser(result.parser_id))
    container.appendChild(tab)
  })
  refreshParserPanel()
}

function refreshParserPanel() {
  if (!isPdfMode) {
    reviewRows = (((parsedData && parsedData.rows) || [])).map((row) => ({ ...row, source_file: importFilename, exclude: !!row.exclude }))
    refreshKeywordStateForRows(reviewRows)
    renderParserWarnings()
    renderParserPreviewTable()
    renderUnknownCatsBannerStep2()
    return
  }
  const result = parserResults.find((parser) => parser.parser_id === selectedParserId)
  if (result) {
    reviewRows = result.rows.map((row) => ({ ...row, source_file: importFilename, exclude: !!row.exclude }))
    refreshKeywordStateForRows(reviewRows)
  }
  renderParserWarnings()
  renderParserPreviewTable()
  renderUnknownCatsBannerStep2()
}

function selectParser(id) {
  const doc = getActiveDoc()
  if (!doc) return
  doc.selectedParserId = id
  selectedParserId = id
  ensureSelectedParserRows(doc)
  syncGlobalsFromActiveDoc()
  document.querySelectorAll(".parser-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.parserId === id))
  refreshParserPanel()
  markDraftDirty()
}

function handleUnknownCatsSelectAll(checked) {
  const banner = document.getElementById("parser-unknown-cats")
  if (!banner) return
  banner.querySelectorAll(".unknown-cat-cb").forEach((checkbox) => {
    checkbox.checked = checked
  })
}

function handleUnknownCatsAction(action) {
  const banner = document.getElementById("parser-unknown-cats")
  if (!banner) return
  const selected = []
  banner.querySelectorAll(".unknown-cat-cb").forEach((checkbox) => {
    if (checkbox.checked) selected.push(checkbox.dataset.cat)
  })
  if (!selected.length) return

  if (action === "autosort") {
    try {
      const settings = JSON.parse(localStorage.getItem("brokeAtmSettings") || "{}")
      const existing = Array.isArray(settings.autoSortCategories) ? settings.autoSortCategories : []
      settings.autoSortCategories = [...new Set([...existing, ...selected])]
      localStorage.setItem("brokeAtmSettings", JSON.stringify(settings))
    } catch (_) {}

    const toast = document.getElementById("import-toast")
    if (toast) {
      toast.innerHTML = `${selected.length} categor${selected.length === 1 ? "y" : "ies"} added to auto-sort list. <a href="/settings" style="color:#fff;text-decoration:underline">Manage in Settings</a>`
      toast.classList.add("show")
      clearTimeout(toast._timer)
      toast._timer = setTimeout(() => {
        toast.classList.remove("show")
        toast.innerHTML = ""
      }, 4000)
    }
  }

  const result = parserResults.find((parser) => parser.parser_id === selectedParserId)
  if (result) {
    result.unknown_pdf_categories = (result.unknown_pdf_categories || []).filter((cat) => !selected.includes(cat))
  }
  const remaining = result ? result.unknown_pdf_categories : []
  if (!remaining.length) {
    banner.classList.add("hidden")
    return
  }
  const list = banner.querySelector("#unknown-cats-list")
  if (list) list.innerHTML = buildUnknownCatRows(remaining)
  markDraftDirty()
}

function handleUnknownCats() {}
function handleUnknownCatsApply() {
  handleUnknownCatsAction("create")
}

function advanceAllParsers() {
  const state = parseStageAdvanceState()
  if (state.disabled) {
    if (state.reason) showAlert(alertsEl, state.reason, "warning")
    return
  }
  importDocs.forEach((doc) => {
    if (doc.status !== "ready") return
    if (doc.isPdfMode) {
      if (!doc.selectedParserId && doc.parserResults && doc.parserResults.length) {
        const recommended = getParserInsightsFor(doc.parserResults).recommended || doc.parserResults[0]
        doc.selectedParserId = recommended ? recommended.parser_id : null
      }
      if (doc.selectedParserId) ensureSelectedParserRows(doc)
    } else if (doc.parsedData && Array.isArray(doc.parsedData.rows)) {
      doc.reviewRows = doc.parsedData.rows.map((row) => ({ ...row }))
      refreshKeywordStateForRows(doc.reviewRows)
    }
    doc.periodReady = true
    doc.reviewReady = false
    doc.step = 3
  })
  syncGlobalsFromActiveDoc()
  markDraftDirty()
  goStep(3)
}

function attachReviewListeners() {
  const chkAllEl = document.getElementById("chk-all")
  if (!chkAllEl || !chkAllEl.parentNode) return
  const chkAllFresh = chkAllEl.cloneNode(true)
  chkAllEl.parentNode.replaceChild(chkAllFresh, chkAllEl)
  chkAllFresh.addEventListener("change", (event) => {
    const want = event.target.checked
    document.querySelectorAll(".row-chk").forEach((checkbox) => {
      const idx = +checkbox.dataset.idx
      const row = reviewRows[idx]
      checkbox.checked = want
      row.exclude = !want
      checkbox.closest("tr").classList.toggle("review-excluded", row.exclude)
      refreshDupHintForRow(idx)
    })
    updateSelectedCount()
    markDraftDirty()
  })

  document.querySelectorAll(".row-chk").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      const idx = +checkbox.dataset.idx
      reviewRows[idx].exclude = !checkbox.checked
      checkbox.closest("tr").classList.toggle("review-excluded", reviewRows[idx].exclude)
      refreshDupHintForRow(idx)
      updateSelectedCount()
      markDraftDirty()
    })
  })
  document.querySelectorAll(".date-inp").forEach((input) => {
    input.addEventListener("change", () => {
      reviewRows[+input.dataset.idx].transaction_date = input.value || null
      markDraftDirty()
    })
  })
  document.querySelectorAll(".merchant-inp").forEach((input) => {
    input.addEventListener("input", () => {
      reviewRows[+input.dataset.idx].merchant_name = input.value
      markDraftDirty()
    })
    input.addEventListener("change", () => {
      const idx = +input.dataset.idx
      refreshKeywordStateForRow(reviewRows[idx])
      renderReviewTable()
      markDraftDirty()
    })
  })
  document.querySelectorAll(".amount-inp").forEach((input) => {
    input.addEventListener("input", () => {
      const value = parseFloat(input.value)
      if (!isNaN(value)) reviewRows[+input.dataset.idx].amount = value
      markDraftDirty()
    })
  })
  document.querySelectorAll(".type-sel").forEach((select) => {
    select.addEventListener("change", () => {
      reviewRows[+select.dataset.idx].transaction_type = select.value
      markDraftDirty()
    })
  })
  document.querySelectorAll(".cat-pick-btn").forEach((button) => {
    button.addEventListener("click", () => {
      void openImportReviewCategoryPicker(+button.dataset.idx)
    })
  })
  document.querySelectorAll(".kw-review-btn").forEach((button) => {
    button.addEventListener("click", () => reviewKeywordConflict(+button.dataset.idx))
  })
  document.querySelectorAll(".notes-inp").forEach((input) => {
    input.addEventListener("input", () => {
      reviewRows[+input.dataset.idx].notes = input.value
      markDraftDirty()
    })
  })
}

async function openImportReviewCategoryPicker(idx) {
  const row = reviewRows[idx]
  if (!row) return
  const picked = await openCategoryPickerModal({
    title: "Set category",
    subtitle: `Search categories for row ${idx + 1}.`,
    searchPlaceholder: "Search categories...",
    selectedValue: row.category_name || row.suggested_category || "",
    actionLabel: "Use",
    items: categories.map((category) => ({
      id: category.id,
      value: category.name,
      name: category.name,
      color: category.color || "",
    })),
    emptyMessage: "No categories available yet.",
    noResultsMessage: (query) => `No categories match "${query}".`,
  })
  if (!picked) return
  row.category_name = picked.name
  const label = document.querySelector(`.cat-pick-btn[data-idx="${idx}"] .category-picker-trigger-label`)
  if (label) label.textContent = reviewCategoryLabel(row)
  markDraftDirty()
}

async function reviewKeywordConflict(idx) {
  const row = reviewRows[idx]
  if (!row || !(row.keyword_matches || []).length) return
  const conflictIndexes = reviewRows
    .map((reviewRow, reviewIdx) => (reviewRow.keyword_resolution_needed ? reviewIdx : -1))
    .filter((reviewIdx) => reviewIdx >= 0)
  const position = conflictIndexes.indexOf(idx)
  const prevIdx = position > 0 ? conflictIndexes[position - 1] : null
  const nextIdx = position >= 0 && position < conflictIndexes.length - 1 ? conflictIndexes[position + 1] : null

  async function applyConflictRemovals({ removals, selectedCategory }) {
    categories = await CategoryKeywordTools.removeKeywords(removals)
    refreshKeywordStateForRows(reviewRows)
    importDocs.forEach((d) => { if (d.reviewRows && d.reviewRows !== reviewRows) refreshKeywordStateForRows(d.reviewRows) })
    const updatedRow = reviewRows[idx]
    if (!updatedRow) {
      renderReviewTable()
      markDraftDirty()
      return { status: "resolved", selectedCategory: "" }
    }

    const remainingMatches = (updatedRow.keyword_matches || []).map((item) => ({
      categoryId: item.category_id != null ? item.category_id : item.categoryId,
      categoryName: item.category_name != null ? item.category_name : item.categoryName,
      keyword: item.keyword,
      length: item.length,
    }))
    const remainingCategories = [...new Set(remainingMatches.map((item) => item.categoryName))].sort()

    if (!remainingCategories.length) {
      updatedRow.category_name = ""
      renderReviewTable()
      markDraftDirty()
      return {
        status: "resolved",
        selectedCategory: "",
        toastMessage: "Set to uncategorized.",
      }
    }

    if (remainingCategories.length === 1) {
      updatedRow.category_name = remainingCategories[0]
      renderReviewTable()
      markDraftDirty()
      return {
        status: "resolved",
        selectedCategory: remainingCategories[0],
        toastMessage: `Set to ${remainingCategories[0]}.`,
      }
    }

    const nextSelectedCategory = remainingCategories.includes(selectedCategory)
      ? selectedCategory
      : remainingCategories[0]
    updatedRow.category_name = nextSelectedCategory
    renderReviewTable()
    markDraftDirty()

    const nextConflictIndexes = reviewRows
      .map((reviewRow, reviewIdx) => (reviewRow.keyword_resolution_needed ? reviewIdx : -1))
      .filter((reviewIdx) => reviewIdx >= 0)
    const nextPosition = nextConflictIndexes.indexOf(idx)

    return {
      status: "multiple",
      matches: remainingMatches,
      selectedCategory: nextSelectedCategory,
      rowIsDuplicate: !!updatedRow.duplicate,
      rowExcluded: !!updatedRow.exclude,
      navigation: {
        current: nextPosition + 1,
        total: nextConflictIndexes.length,
        hasPrev: nextPosition > 0,
        hasNext: nextPosition >= 0 && nextPosition < nextConflictIndexes.length - 1,
      },
    }
  }

  const result = await openMerchantKeywordModal({
    title: "Resolve category conflict",
    merchantName: row.merchant_name,
    normalizedMerchant: row.normalized_merchant,
    matches: row.keyword_matches.map((item) => ({
      categoryId: item.category_id != null ? item.category_id : item.categoryId,
      categoryName: item.category_name != null ? item.category_name : item.categoryName,
      keyword: item.keyword,
      length: item.length,
    })),
    selectedCategory: row.category_name || row.suggested_category || "",
    rowIsDuplicate: !!row.duplicate,
    rowExcluded: !!row.exclude,
    navigation: {
      current: position + 1,
      total: conflictIndexes.length,
      hasPrev: prevIdx != null,
      hasNext: nextIdx != null,
    },
    onApplyRemovals: applyConflictRemovals,
  })
  if (!result) return
  if (result.selectedCategory) {
    row.category_name = result.selectedCategory
  }
  if (result.action === "done") {
    row.keyword_resolution_needed = false
    row.keyword_conflict_categories = false
  }
  if (result.action === "prev" && prevIdx != null) {
    await reviewKeywordConflict(prevIdx)
    return
  }
  if (result.action === "next" && nextIdx != null) {
    await reviewKeywordConflict(nextIdx)
    return
  }
  if (result.action === "remove") {
    // applyConflictRemovals already updated rows, rendered table, and marked dirty
    const updatedState = result.updatedState
    if (updatedState?.status === "multiple") {
      // This row still has unresolved conflicts after the removal — re-open it
      await reviewKeywordConflict(idx)
    } else {
      // Row resolved; find the next remaining conflict
      const remaining = reviewRows
        .map((r, i) => (r.keyword_resolution_needed ? i : -1))
        .filter((i) => i >= 0)
      if (remaining.length > 0) {
        await reviewKeywordConflict(remaining[0])
      }
    }
    return
  }
  if (result.action === "done") {
    renderReviewTable()
    markDraftDirty()
    const remaining = reviewRows
      .map((r, i) => (r.keyword_resolution_needed ? i : -1))
      .filter((i) => i >= 0)
    if (remaining.length > 0) {
      await reviewKeywordConflict(remaining[0])
    }
    return
  }
  if (result.action === "close") {
    renderReviewTable()
    markDraftDirty()
  }
}

function syncReviewMasterCheckbox() {
  const el = document.getElementById("chk-all")
  if (!el || !reviewRows.length) return
  const selected = reviewRows.filter((row) => !row.exclude).length
  el.checked = selected === reviewRows.length
  el.indeterminate = selected > 0 && selected < reviewRows.length
}

function updateSelectedCount() {
  const selected = reviewRows.filter((row) => !row.exclude).length
  const text = `${selected} of ${reviewRows.length} selected`
  document.querySelectorAll(".review-selected-count").forEach((el) => {
    el.textContent = text
  })
  syncReviewMasterCheckbox()
}

function commitRowsForDoc(doc) {
  prepareDocForReview(doc)
  const rows = doc.reviewRows.map((row) => ({ ...row }))
  applyImportPeriodsToRows(rows, doc)
  return rows
}

function validationMessageForDocs(docsWithRows) {
  const problems = []
  docsWithRows.forEach(({ doc, rows }) => {
    rows.forEach((row, i) => {
      if (row.exclude) return
      const missing = rowMissingRequired(row)
      if (!missing.length) return
      problems.push(`${doc.filename} row ${i + 1}: missing ${missing.join(", ")}`)
    })
  })
  if (!problems.length) return ""
  const preview = problems.slice(0, 5).join("; ")
  const more = problems.length > 5 ? ` and ${problems.length - 5} more` : ""
  return `${problems.length} row${problems.length !== 1 ? "s" : ""} have missing required fields. ${preview}${more}.`
}

function setButtonBusy(buttons, busyText) {
  buttons.forEach((button) => {
    if (!button.dataset.defaultLabel) button.dataset.defaultLabel = button.textContent
    button.disabled = true
    button.textContent = busyText
  })
}

function resetButtonBusy(buttons) {
  buttons.forEach((button) => {
    button.disabled = false
    button.textContent = button.dataset.defaultLabel || button.textContent
  })
}

function finishImport(docsToRemove, result, titlePrefix) {
  const ids = new Set(docsToRemove.map((doc) => doc.id))
  importDocs = importDocs.filter((doc) => !ids.has(doc.id))
  void deleteDraftFiles([...ids])

  const batchNote =
    result.batch_ids && result.batch_ids.length > 1
      ? ` (${result.batch_ids.length} import batches)`
      : ""
  const batchId = result.batch_id ? ` Batch ${String(result.batch_id).slice(0, 8)}…` : ""
  doneSummary = {
    title: "Import complete",
    summary: `${titlePrefix}${result.imported} imported, ${result.skipped} skipped${batchNote}.${batchId}`,
  }

  if (!importDocs.length) {
    activeDocId = null
    currentStep = 5
    renderApp()
    updateHistory({ replace: true })
    scheduleDraftSave()
    return
  }

  showAlert(alertsEl, `${titlePrefix}${result.imported} imported, ${result.skipped} skipped.`, "success")
  focusBestRemainingDoc({ replaceHistory: true })
  scheduleDraftSave()
}

async function runCommitAll() {
  const buttons = [document.getElementById("btn-stage-primary")].filter(Boolean)
  setButtonBusy(buttons, "Importing…")
  try {
    await refreshDuplicatesAcrossDocs()
    const docs = getReadyDocs()
    if (!docs.length) {
      showAlert(alertsEl, "No ready files to import yet.", "warning")
      return
    }
    const docsWithRows = docs.map((doc) => ({ doc, rows: commitRowsForDoc(doc) }))
    const validation = validationMessageForDocs(docsWithRows)
    if (validation) {
      showAlert(alertsEl, validation, "error")
      return
    }
    const result = await API.commitImport({
      filename: docs.length === 1 ? docs[0].filename : "multi import",
      month: (docs[0].parsedData && docs[0].parsedData.detected_month) || 1,
      year: (docs[0].parsedData && docs[0].parsedData.detected_year) || 2000,
      rows: docsWithRows.flatMap((item) => item.rows),
    })
    finishImport(docs, result, docs.length === 1 ? `${docs[0].filename}: ` : "")
  } catch (error) {
    showAlert(alertsEl, error.message, "error")
  } finally {
    resetButtonBusy(buttons)
  }
}

async function handleQueuePrimaryAction() {
  if (currentStep === 2) {
    advanceAllParsers()
    return
  }
  if (currentStep === 3) {
    await runDuplicateCheckAndGoReview()
    return
  }
  if (currentStep === 4) {
    await runCommitAll()
  }
}

function resetImport() {
  importDocs = []
  activeDocId = null
  currentStep = 1
  doneSummary = null
  parsedData = null
  reviewRows = []
  importFilename = ""
  isPdfMode = false
  selectedParserId = null
  parserResults = []
  fileInput.value = ""
  void clearImportDraftStorage()
  renderApp()
  updateHistory({ replace: true })
}

function bindEvents() {
  dropZone.addEventListener("click", () => fileInput.click())
  dropZone.addEventListener("dragover", (event) => {
    event.preventDefault()
    dropZone.classList.add("drag-over")
  })
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"))
  dropZone.addEventListener("drop", (event) => {
    event.preventDefault()
    dropZone.classList.remove("drag-over")
    const files = [...event.dataTransfer.files].filter(isSupportedImportFile)
    if (files.length) handleFileList(files)
  })
  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files.length) handleFileList(fileInput.files)
  })

  const stageBackBtn = document.getElementById("btn-stage-back")
  const stagePrimaryBtn = document.getElementById("btn-stage-primary")
  const selectAllBtn = document.getElementById("btn-select-all")
  const deselectAllBtn = document.getElementById("btn-deselect-all")
  const reviewKeywordBtn = document.getElementById("btn-review-keyword-conflicts")
  const addEntryBtn = document.getElementById("btn-add-entry-import")

  if (stageBackBtn) stageBackBtn.addEventListener("click", () => {
    goStep(+stageBackBtn.dataset.step || previousStepFor(currentStep))
  })
  if (stagePrimaryBtn) stagePrimaryBtn.addEventListener("click", async () => {
    const button = document.getElementById("btn-stage-primary")
    if (!button || button.disabled) return
    const stepAtClick = currentStep
    if (stepAtClick === 3) setButtonBusy([button], "Checking…")
    try {
      await handleQueuePrimaryAction()
    } catch (error) {
      showAlert(alertsEl, error.message, "error")
    } finally {
      if (stepAtClick === 3) resetButtonBusy([button])
      renderStageToolbar()
      renderStageActionButtons()
    }
  })
  if (selectAllBtn) selectAllBtn.addEventListener("click", () => {
    reviewRows.forEach((row, i) => {
      row.exclude = false
      const checkbox = document.querySelector(`.row-chk[data-idx="${i}"]`)
      if (checkbox) {
        checkbox.checked = true
        checkbox.closest("tr").classList.toggle("review-excluded", false)
      }
      refreshDupHintForRow(i)
    })
    updateSelectedCount()
    markDraftDirty()
  })
  if (deselectAllBtn) deselectAllBtn.addEventListener("click", () => {
    reviewRows.forEach((row, i) => {
      row.exclude = true
      const checkbox = document.querySelector(`.row-chk[data-idx="${i}"]`)
      if (checkbox) {
        checkbox.checked = false
        checkbox.closest("tr").classList.toggle("review-excluded", true)
      }
      refreshDupHintForRow(i)
    })
    updateSelectedCount()
    markDraftDirty()
  })
  if (reviewKeywordBtn) reviewKeywordBtn.addEventListener("click", async () => {
    const idx = reviewRows.findIndex((row) => row.keyword_resolution_needed)
    if (idx >= 0) await reviewKeywordConflict(idx)
  })
  if (addEntryBtn) addEntryBtn.addEventListener("click", () => {
    openAddTxModal({
      onSuccess: (count) => {
        showAlert(
          alertsEl,
          count === 1 ? "Entry added successfully." : `${count} entries added successfully.`,
          "success"
        )
      },
    })
  })

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      void persistImportDraftNow()
    }
  })
}

async function init() {
  categories = await API.getCategories()
  processRecurringOnLoad()
  bindEvents()
  const restored = await restoreImportDraft()
  initializeHistory()
  renderApp()
  if (restored) {
    scheduleDraftSave()
    showAlert(alertsEl, `Restored ${importDocs.length} import file${importDocs.length !== 1 ? "s" : ""}.`, "success")
    if (importDocs.some((doc) => doc.status === "queued")) {
      void processQueue()
    }
  }
}

init().catch((error) => {
  showAlert(alertsEl, error.message || "Import page failed to load.", "error")
})
