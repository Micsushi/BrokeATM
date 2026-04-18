# BrokeATM

For those that are broke at the moment to be less broke in the future

---

## Features

- **CSV & PDF Import**: Drop a CSV or bank PDF, auto-detect the month/year, review and edit every row before saving
- **Flexible Parsing**: Auto-detects column names from CIBC, TD, RBC, Scotiabank, Chase, and most other banks
- **Duplicate Detection**: Warns you if a row already exists in the database (matched by reference number)
- **Smart Categorization**: Automatically maps MCC (merchant category) descriptions to friendly category names on import
- **Budgets**: Set monthly spending limits per category and track progress
- **Dashboard**: Expense + income pie charts per category, bar chart of last N months
- **`atm` command**: Start the app from any terminal on your machine with a single word

---

## Setup

### Prerequisites

- **Python 3.11+**: https://www.python.org/downloads/ — check "Add Python to PATH" during install

**For PDF imports** (optional — CSV works without these):

| Tool | Download |
|---|---|
| Java JRE 8+ | https://adoptium.net/ |
| Tesseract OCR | https://github.com/UB-Mannheim/tesseract/wiki |
| Poppler | https://github.com/oschwartz10612/poppler-windows/releases |
| Ghostscript | https://www.ghostscript.com/releases/ |

Parsers with missing dependencies show as inactive in the UI — the rest still run.

### Install

```powershell
git clone https://github.com/micsushi/BrokeATM.git
cd BrokeATM
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\alembic upgrade head
```

> First install can take several minutes (includes ML/OCR libraries).

### Register the `atm` command (one-time)

```powershell
$scriptsPath = "$PWD\.venv\Scripts"
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
[Environment]::SetEnvironmentVariable("PATH", "$scriptsPath;$currentPath", "User")
```

Close and reopen your terminal, then run `atm`.

---

## Running

```
atm                   # start on port 8000
atm --port 9000       # different port
atm --no-browser      # don't open browser
atm --reload          # dev mode
```

---

## Data

Data is stored at `C:\Users\<YourName>\.brokeatm\brokeatm.db`. To back up, copy that file.

To use a different location, set `ATM_DATA_DIR` in a `.env` file in the project root.

---

## Troubleshooting

**`atm` not recognized**: close and reopen terminal. If still failing, re-run the PATH command above.

**`atm` breaks after moving the folder**: re-run the PATH command from the new location, then run `.venv\Scripts\pip install -e .`

**Port in use**: `atm --port 9000`

**Unrecognized CSV format**: check the first row of your CSV against `FIELD_ALIASES` in `app/services/csv_parser.py` and add your bank's headers.

**PDF returns 0 rows**: install missing PDF dependencies, or export as CSV instead.

**easyocr/torch install fails**:
```powershell
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\pip install -e ".[dev]"
```
