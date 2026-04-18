# BrokeATM

A local web app for importing, tracking, and visualizing personal expenses and income. Runs entirely on your machine: no cloud, no accounts, no subscriptions.

---

## Features

- **CSV & PDF Import**: Drop a CSV or bank PDF, auto-detect the month/year, review and edit every row before saving
- **Flexible Parsing**: Auto-detects column names from CIBC, TD, RBC, Scotiabank, Chase, and most other banks
- **Duplicate Detection**: Warns you if a row already exists in the database (matched by reference number)
- **Smart Categorization**: Automatically maps MCC (merchant category) descriptions to friendly category names on import
- **Categories**: Create, rename, recolor, and merge categories; all stored lowercase so "Food" and "food" are the same
- **Multi-account**: Each import is linked to a card/account, tracked separately
- **Budgets**: Set monthly spending limits per category and track progress
- **Records View**: Filter by month, year, type, category, account; search by merchant; inline edit, bulk edit, bulk delete, add entries manually
- **Dashboard**: Expense + income pie charts per category, bar chart of last N months
- **`atm` command**: Start the app from any terminal on your machine with a single word

---

## Quick Start (summary)

```
1. Install Python 3.11+
2. Clone repo and cd into it
3. python -m venv .venv
4. Install dependencies
5. Run database migrations
6. Add .venv/Scripts (Windows) or .venv/bin (Mac/Linux) to PATH
7. Type: atm
```

Full step-by-step for each OS below.

---

## Installation

### Prerequisites

| Requirement | Why | Download |
|---|---|---|
| **Python 3.11+** | Runs the app | https://www.python.org/downloads/ |
| **Git** (optional) | Cloning the repo | https://git-scm.com/ |

**For PDF imports only** (CSV works without these):

| Requirement | Why | Where |
|---|---|---|
| **Java JRE 8+** | tabula-py table extraction | https://adoptium.net/ |
| **Tesseract OCR** | OCR-based PDF parsing | See OS-specific steps below |
| **Poppler** | PDF-to-image conversion | See OS-specific steps below |
| **Ghostscript** | camelot lattice mode | https://www.ghostscript.com/releases/ |

> If you only import CSVs, skip the PDF-only tools. The app works fine without them.

---

## Setup: Windows

### Step 1: Install Python

1. Download from https://www.python.org/downloads/ and run the installer
2. **On the first screen, check "Add Python to PATH"** before clicking Install — this is required

Verify in a new PowerShell window:
```powershell
python --version
```
You should see `Python 3.11.x` or newer.

### Step 2: Get the project

**Option A: Clone with Git**
```powershell
cd C:\Users\<YourName>\Documents
git clone https://github.com/your-username/BrokeATM.git
cd BrokeATM
```

**Option B: Download ZIP**

Download and extract the ZIP from GitHub. Open PowerShell, then `cd` into the extracted folder.

### Step 3: Create a virtual environment

```powershell
python -m venv .venv
```

This creates an isolated Python environment inside the project folder so dependencies don't collide with anything else on your machine.

### Step 4: Install dependencies

```powershell
.venv\Scripts\pip install -e ".[dev]"
```

Installs all packages the app needs. The `-e` flag means source files are used directly so code changes take effect without reinstalling. `[dev]` also installs the linter and test tools.

> The first install can take several minutes — it includes ML/OCR libraries (easyocr, torch). This is normal.

### Step 5: Set up the database

```powershell
.venv\Scripts\alembic upgrade head
```

Creates the SQLite database at `C:\Users\<YourName>\.brokeatm\brokeatm.db` and sets up all tables. Run this once, and again after any schema changes.

### Step 6: Register the `atm` command (one-time)

This adds the virtual environment's `Scripts` folder to your user PATH so you can type `atm` from any terminal — no need to activate the venv or navigate to the project folder.

**Run this from the project folder in PowerShell:**

```powershell
$scriptsPath = "$PWD\.venv\Scripts"
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
[Environment]::SetEnvironmentVariable("PATH", "$scriptsPath;$currentPath", "User")
```

**Close and reopen your terminal.** PATH changes only apply to new sessions.

Verify it worked:
```powershell
atm --help
```

### Step 7: Run the app

From any terminal, any folder:
```powershell
atm
```

The browser opens automatically at http://localhost:8000. Press `Ctrl+C` to stop.

---

## Setup: macOS

### Step 1: Install Python

**Option A: Homebrew (recommended)**
```bash
brew install python@3.11
```

**Option B: Installer**
Download from https://www.python.org/downloads/ and run the `.pkg`.

Verify:
```bash
python3 --version
```

### Step 2: Get the project

```bash
cd ~/Documents
git clone https://github.com/your-username/BrokeATM.git
cd BrokeATM
```

### Step 3: Create a virtual environment

```bash
python3 -m venv .venv
```

### Step 4: Install dependencies

```bash
.venv/bin/pip install -e ".[dev]"
```

### Step 5: Set up the database

```bash
.venv/bin/alembic upgrade head
```

Creates the database at `~/.brokeatm/brokeatm.db`.

### Step 6: Register the `atm` command (one-time)

Add the venv `bin` folder to your PATH. Run this from the project folder:

```bash
echo "export PATH=\"$PWD/.venv/bin:\$PATH\"" >> ~/.zshrc
source ~/.zshrc
```

If you use Bash instead of Zsh, replace `~/.zshrc` with `~/.bash_profile`.

> The path above is absolute, so `atm` will break if you move the project folder. Re-run this step from the new location if you move it.

Verify:
```bash
atm --help
```

### Step 7: Run the app

```bash
atm
```

---

## Setup: Linux

### Step 1: Install Python

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install python3.11 python3.11-venv python3-pip
```

**Fedora:**
```bash
sudo dnf install python3.11
```

Verify:
```bash
python3.11 --version
```

### Step 2: Get the project

```bash
cd ~/Documents
git clone https://github.com/your-username/BrokeATM.git
cd BrokeATM
```

### Step 3: Create a virtual environment

```bash
python3.11 -m venv .venv
```

### Step 4: Install dependencies

```bash
.venv/bin/pip install -e ".[dev]"
```

### Step 5: Set up the database

```bash
.venv/bin/alembic upgrade head
```

### Step 6: Register the `atm` command (one-time)

Run this from the project folder:

```bash
echo "export PATH=\"$PWD/.venv/bin:\$PATH\"" >> ~/.bashrc
source ~/.bashrc
```

Verify:
```bash
atm --help
```

### Step 7: Run the app

```bash
atm
```

---

## Running the App

```
atm                   # start on port 8000, open browser automatically
atm --port 9000       # use a different port if 8000 is taken
atm --no-browser      # start without opening the browser
atm --reload          # dev mode: auto-restart when you change code
atm --help            # show all options
```

The browser opens automatically at http://localhost:8000. Press `Ctrl+C` in the terminal to stop.

---

## Using the App

### Import tab: adding transactions

1. Drop a CSV or PDF file onto the upload area (or click to browse)
2. The app detects the month/year from the dates; confirm or change it
3. Review the rows: every field is editable inline. Tab through cells to move quickly
4. Uncheck rows you don't want to import (payments are unchecked by default)
5. Click **Import Selected**

You can also add a single entry manually with the **+ Add Entry** button on the Import or Records page — no file needed.

### Records tab: browsing and editing

- Filter by **month/year**, **type** (expense/income/refund/transfer), **category**, **account**, or free-text **search**
- The totals bar at the top updates to reflect your current filters:
  - Expenses includes refunds
  - Income shows only income
  - Net excludes transfers
  - Transfers shown separately
- Click **Edit** on any row to change any field
- Select multiple rows with checkboxes for **bulk delete**, **bulk category change**, or **bulk type change**
- The header checkbox selects/deselects the whole page

### Categories tab: managing categories

- Categories are created automatically from MCC descriptions when you import
- You can rename, recolor, or merge any category
- Merging moves all transactions from one category into another, then deletes the source
- Category names are always stored lowercase — "Dining" and "dining" are the same

### Budget tab: monthly spending limits

- Set a monthly budget per category
- Progress bars show how much of each budget you've used for the selected month

### Dashboard tab: charts

- **Totals & Pie Charts**: select one or more months; defaults to the most recent completed month
- **Bar Chart**: select a range of months; defaults to the last 6 months including the current one
- Pie slices under 5% of the total are grouped into an "Other" slice (hover to see what's inside)
- Legends show both the dollar amount and percentage for each slice

---

## Transaction Types

| Type | When it's used |
|---|---|
| **Expense** | Any positive charge (default) |
| **Income** | Money coming in (salary, e-transfer received, etc.) |
| **Refund** | Negative amount or cashback credit |
| **Transfer** | Credit card payments ("PAYMENT THANK YOU"); excluded from net balance |

The app classifies these automatically on import based on the amount sign and merchant name. You can change any row's type in the review step or later in Records.

---

## Supported File Formats

### CSV

Column headers are matched case-insensitively:

| Bank | Key headers used |
|---|---|
| CIBC credit card | `Date`, `Merchant Name`, `Amount` |
| TD chequing/savings | `Transaction Date`, `Description`, `Debit`, `Credit` |
| RBC | `Transaction Date`, `Description 1`, `CAD$ Amount` |
| Scotiabank | `Date`, `Description`, `Withdrawals`, `Deposits` |
| Chase | `Post Date`, `Payee`, `Amount` |
| Generic | Any CSV with a date column + amount column (or debit/credit columns) |

If your bank uses different column names, open [app/services/csv_parser.py](app/services/csv_parser.py), find `FIELD_ALIASES`, and add your bank's headers.

### PDF (bank statements)

The app tries multiple extraction strategies and picks the one with highest confidence:

1. `pdfplumber` table extraction
2. `camelot` lattice mode (requires Ghostscript)
3. `camelot` stream mode
4. `tabula` (requires Java JRE)
5. `pdfplumber` coordinate-based text parsing
6. `tesseract` OCR (requires Tesseract + Poppler)
7. `easyocr` deep-learning OCR (slowest, most accurate fallback)

#### Installing PDF system dependencies

**Tesseract OCR:**
- Windows: download installer from https://github.com/UB-Mannheim/tesseract/wiki, install to the default location, then add `C:\Program Files\Tesseract-OCR` to your PATH
- macOS: `brew install tesseract`
- Ubuntu/Debian: `sudo apt install tesseract-ocr`

**Poppler (for pdf2image):**
- Windows: download from https://github.com/oschwartz10612/poppler-windows/releases, extract, and add the `bin` folder to your PATH
- macOS: `brew install poppler`
- Ubuntu/Debian: `sudo apt install poppler-utils`

**Java JRE (for tabula):**
- All platforms: download from https://adoptium.net/ and install. Verify with `java -version`.

**Ghostscript (for camelot lattice mode):**
- Windows: download installer from https://www.ghostscript.com/releases/
- macOS: `brew install ghostscript`
- Ubuntu/Debian: `sudo apt install ghostscript`

---

## Data Storage

All data lives at a fixed location regardless of where you run `atm`:

```
~/.brokeatm/
  brokeatm.db    - SQLite database (transactions, categories, accounts, budgets)
  uploads/       - temporary files from imports (safe to delete anytime)
```

On Windows: `C:\Users\<YourName>\.brokeatm\`

To back up your data: copy `brokeatm.db`. To restore: put it back in the same place.

### Custom data directory

Set `ATM_DATA_DIR` to change where data is stored:

```powershell
# Windows: current session only
$env:ATM_DATA_DIR = "D:\Backups\brokeatm"
atm
```

```bash
# macOS/Linux: current session
ATM_DATA_DIR=~/Backups/brokeatm atm
```

Or add it permanently to a `.env` file in the project root:
```
ATM_DATA_DIR=D:\Backups\brokeatm
```

---

## Troubleshooting

**`atm` is not recognized after setup**

Close and reopen your terminal. If it still fails:
- Windows: run `echo $env:PATH` and check that `.venv\Scripts` appears
- macOS/Linux: run `echo $PATH` and check that `.venv/bin` appears

Re-run the Step 6 PATH command if it's missing, then open a new terminal.

**`atm` stops working after moving the project folder**

The PATH entry points to the absolute path of `.venv\Scripts` (or `.venv/bin`). After moving, `cd` into the new location, re-run the Step 6 PATH command, then run `pip install -e .` from inside the venv.

**Port 8000 is already in use**

Run `atm --port 9000` (or any free port).

**Database is empty after switching machines**

Copy `~/.brokeatm/brokeatm.db` from the old machine to the same path on the new one. Then run `alembic upgrade head` once on the new machine to ensure the schema is current.

**Import fails with "Unrecognized CSV format"**

Your CSV doesn't have a column matching any known date or amount header. Open the file in a text editor, check the first row (the headers), and compare against `FIELD_ALIASES` in [app/services/csv_parser.py](app/services/csv_parser.py). Add your bank's headers there.

**PDF import returns 0 rows or very low confidence**

None of the extraction strategies could parse the PDF reliably. Try:
1. Verify Java, Tesseract, Poppler, and Ghostscript are installed and on your PATH
2. Open the PDF in a browser — if you can't select text in it, it's a scanned image (OCR is required)
3. Export from your bank as CSV instead — always more reliable than PDF

**easyocr/torch install is very slow or fails**

These are large ML packages; the first install can take 10-20 minutes. If it fails:
```powershell
# Windows
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\pip install -e ".[dev]"
```
```bash
# macOS/Linux
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -e ".[dev]"
```

---

## Development

```powershell
# Lint
.venv\Scripts\ruff check .

# Format
.venv\Scripts\ruff format .

# Run tests
.venv\Scripts\pytest

# After changing a model, generate and apply a migration:
.venv\Scripts\alembic revision --autogenerate -m "describe the change"
.venv\Scripts\alembic upgrade head
```

### Project structure

```
app/
  api/               - FastAPI route handlers (one file per resource)
  cli.py             - `atm` command entry point
  core/
    config.py        - App settings (data dir, db URL)
    database.py      - SQLAlchemy engine and session
    schemas.py       - Pydantic request/response models
    utils.py         - Shared utilities
  models/
    models.py        - SQLAlchemy ORM models (Transaction, Category, Account, ImportBatch, Budget)
  services/
    csv_parser.py        - CSV column detection, date/amount parsing, row classification
    import_service.py    - Commit parsed rows to the database
    mcc_map.py           - MCC description to category name mapping
    budget_service.py    - Budget calculations
    keyword_matching.py  - Keyword-based auto-categorization
    parsers/             - PDF extraction strategies (pdfplumber, camelot, tabula, OCR)
  static/
    css/main.css     - Global dark-theme styles
    js/api.js        - Frontend API wrapper
    js/utils.js      - Shared helpers (formatting, badges, alerts)
  templates/         - HTML pages (index, records, categories, dashboard, budget)
  main.py            - FastAPI app, mounts static files, registers routers
migrations/          - Alembic migration scripts
pyproject.toml       - Dependencies, build config, Ruff settings
```
