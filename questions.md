# Import Page Bug Fixes

## Bug 1: Changing tabs is unresponsive while files are parsing

**Problem:**
When a file was processing and you clicked on a different file tab, the UI would snap you back to the processing file as soon as it finished. Root cause: `shouldAutoOpenDoc()` returned `true` whenever the currently-active doc had status `queued`, `processing`, or `error`. So even if you manually navigated to a different doc (which happened to be queued), completing doc A would override your choice and redirect you back to it.

**Fix:**
Removed the last `return` condition in `shouldAutoOpenDoc`. Now it only auto-opens a doc if there is no active doc at all, the finishing doc IS already the active doc, or the user is on step 1. Once you manually click a tab, the queue never redirects you away.

---

## Bug 2: PDF with UUID filename shows "Choose parser" with 0 parsers

**Problem:**
The file `9ee416b6-...-9550dfd24fef.pdf` is likely a scanned/image-only PDF. Text-based parsers all run but extract 0 rows. The old code only threw an error when NO parsers ran at all (`results.length === 0`), not when all parsers returned 0 rows. So the doc landed in "ready" state with empty parser options - confusing, since "Choose parser" appeared with nothing to actually choose.

**Fix:**
After getting parser results, check if `maxRows === 0` (every parser found 0 rows). If so, throw an error with a clear message: "No rows could be extracted from this file. It may be a scanned/image PDF that requires OCR, or an unsupported format." The doc now shows "Needs attention" with a proper error message instead of a dead "Choose parser" state.

---

## Bug 3: "Choose parsers" button appeared twice in step 2

**Problem:**
The import queue header had a dynamic action button (`btn-import-all-files`) that mirrored the current stage's primary action. It was shown for steps 2, 3, and 4. But step 2 already has `btn-use-parser` inside the step content doing the exact same thing. This caused the "Choose parsers for 1 file" label to appear both at the top-right of the queue and at the bottom of the step.

**Fix:**
Changed the header button visibility to only show on steps 3 and 4 (`currentStep >= 3`). Step 2 uses `btn-use-parser` in the step content exclusively.

---

## Bug 4: File periods step only showed the active file, not all files

**Problem:**
`renderFilePeriodPickers()` only looked at `getActiveDoc()` and rendered pickers for that doc's source files. With multiple files in a batch, you'd only see month/year for whichever file was currently focused - the others were invisible and couldn't be set.

**Fix:**
Rewrote `renderFilePeriodPickers()` to iterate over ALL ready docs in the batch (`importDocs.filter(d => d.status === "ready")`). Each period picker row now has a `data-doc-id` attribute scoping it to its doc. `syncPerFilePeriodFromPickers(doc)` was updated to query `[data-doc-id="${doc.id}"]` so it reads back only the right doc's pickers, not all rows. `renderStepPanels` no longer gates step 3 rendering on `activeDoc.parsedData`.

---

## Bug 5: Files added via "Add more files" while batch was processing would stay stuck as "Queued"

**Problem:**
`processQueue()` has a guard: `if (queueProcessing) return`. When new files were added while the original batch was processing, `handleFileList` called `processQueue()` which returned immediately. The running queue's `while` loop would normally pick up new queued docs on its next iteration - but there was a narrow timing window where the loop could check for queued docs, find none (before the new docs were pushed), and exit. The `finally` block set `queueProcessing = false` but never restarted the loop. New docs stayed as "Queued" until the page was reloaded, at which point `init()` detected queued docs and re-ran `processQueue()`.

**Fix:**
Added a safety check after the `finally` block in `processQueue()`: if any docs are still in "queued" status after the loop exits naturally, call `void processQueue()` again. Since `queueProcessing` is already `false` at that point, it runs a fresh loop and picks up the stragglers.
