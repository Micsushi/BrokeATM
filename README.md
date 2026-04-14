# BrokeATM

A local web app for importing, tracking, and visualizing personal expenses and income. Runs entirely on your machine: no cloud, no accounts, no subscriptions.

---

## Features

- **CSV Import**: Drop a CSV, auto-detect the month/year, review and edit every row before saving
- **Flexible CSV Parsing**: Auto-detects column names from CIBC, TD, RBC, Scotiabank, Chase, and most other banks
- **Duplicate Detection**: Warns you if a row already exists in the database (matched by reference number)
- **Smart Categorization**: Automatically maps MCC (merchant category) descriptions to friendly category names on import
- **Categories**: Create, rename, recolor, and merge categories; all stored in lowercase so "Food" and "food" are the same
- **Multi-account**: Each import is linked to a card/account, tracked separately
- **Records View**: Filter by month, year, type, category, account; search by merchant; inline edit, bulk edit, bulk delete, add entries manually
- **Dashboard**: Expense + income pie charts per category (slices under 5% grouped into "other"), bar chart of last N months
- **`atm` command**: Start the app from any terminal on your machine with a single word

---

## First-time Setup

### Prerequisites

- **Python 3.11 or newer**: https://www.python.org/downloads/
  - On Windows: check **"Add Python to PATH"** during installation
- **Git** (optional, only needed to clone): https://git-scm.com/

### 1. Get the project

```powershell
cd C:\Users\<you>\Documents\Github
git clone <repo-url> BrokeATM
cd BrokeATM
```

Or download and extract the ZIP, then `cd` into the folder.

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

This creates an isolated Python environment inside the project folder so dependencies don't conflict with anything else on your machine.

### 3. Install dependencies

```powershell
.venv\Scripts\pip install -e ".[dev]"
```

The `-e` flag installs in "editable" mode: the source files are used directly, so any changes you make take effect immediately without reinstalling. `[dev]` also installs the linter and test tools.

### 4. Set up the database

```powershell
.venv\Scripts\alembic upgrade head
```

This creates the SQLite database file at `~/.brokeatm/brokeatm.db` and sets up all the tables. You only need to run this once (and again after any schema changes).

### 5. Add `atm` to your PATH (one-time)

This lets you type `atm` from any terminal without activating the venv first.

```powershell
$scriptsPath = "$PWD\.venv\Scripts"
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
[Environment]::SetEnvironmentVariable("PATH", "$scriptsPath;$currentPath", "User")
```

> **Important:** Close and reopen your terminal after running this. The PATH change only applies to new terminal sessions.

---

## Running the App

Open any terminal (no need to be in the project folder) and run:

```powershell
atm
```

The browser opens automatically at http://localhost:8000. Press `Ctrl+C` in the terminal to stop.

### Options

```powershell
atm --port 9000       # use a different port if 8000 is taken
atm --no-browser      # start without opening the browser
atm --reload          # dev mode: auto-restart when you change code
atm --help            # show all options
```

---

## Using the App

### Import tab — adding transactions

1. Drop a CSV file onto the upload area (or click to browse)
2. The app detects the month/year from the dates; confirm or change it
3. Review the rows: every field is editable inline. Tab through cells to move quickly
4. Uncheck rows you don't want to import (payments are unchecked by default)
5. Click **Import Selected**

You can also add a single entry manually using the **+ Add Entry** button on the Import page or the Records page (no CSV needed).

### Records tab — browsing and editing

- Filter by **month/year**, **type** (expense/income/refund/transfer), **category**, **account**, or free-text **search**
- The **totals bar** at the top updates to reflect your current filters:
  - Expenses includes refunds
  - Income shows only income
  - Net excludes transfers
  - Transfers shown separately
- Click **Edit** on any row to change any field
- Select multiple rows with the checkboxes for **bulk delete**, **bulk category change**, or **bulk type change**
- The header checkbox selects/deselects the whole page

### Categories tab — managing categories

- Categories are created automatically from MCC descriptions when you import
- You can rename, recolor, or merge any category
- Merging moves all transactions from one category into another, then deletes the source
- Category names are always stored lowercase, so "Dining" and "dining" are the same

### Dashboard tab — charts

- **Totals & Pie Charts**: select one or more months; defaults to the most recent completed month
- **Bar Chart**: select a range of months; defaults to the last 6 months including the current one
- Pie slices under 5% of the total are grouped into an "Other" slice (hover to see what's inside)
- Legends show both the dollar amount and percentage for each slice

---

## Transaction Types

| Type | When it's used |
|---|---|
| **Expense** | Any positive charge (default) |
| **Income** | Money coming in (e.g. salary, e-transfer received) |
| **Refund** | Negative amount or cashback credit |
| **Transfer** | Credit card payments ("PAYMENT THANK YOU"); excluded from net balance |

The app classifies these automatically on import based on the amount sign and merchant name. You can change any row's type in the review step or later in Records.

---

## Data Storage

All data lives in a fixed location on your machine:

```
C:\Users\<you>\.brokeatm\
  brokeatm.db    - SQLite database (all your transactions, categories, accounts)
  uploads\       - temporary files from CSV imports
```

This location never changes regardless of where you run `atm` from. To back up your data, copy `brokeatm.db`.

### Using a custom data directory

Set the `ATM_DATA_DIR` environment variable:

```powershell
# For the current session only:
$env:ATM_DATA_DIR = "D:\Backups\brokeatm"
atm

# Permanently (add to a .env file in the project root):
ATM_DATA_DIR=D:\Backups\brokeatm
```

---

## Supported CSV Formats

Column headers are matched case-insensitively. The following banks are recognized out of the box:

| Bank | Key headers used |
|---|---|
| CIBC credit card | `Date`, `Merchant Name`, `Amount` |
| TD chequing/savings | `Transaction Date`, `Description`, `Debit`, `Credit` |
| RBC | `Transaction Date`, `Description 1`, `CAD$ Amount` |
| Scotiabank | `Date`, `Description`, `Withdrawals`, `Deposits` |
| Chase | `Post Date`, `Payee`, `Amount` |
| Generic | Any CSV with a date column + amount column (or debit/credit columns) |

If your bank uses different header names, check `app/services/csv_parser.py` under `FIELD_ALIASES` and add your bank's column names to the relevant list.

---

## Development

```powershell
# Lint
.venv\Scripts\ruff check .

# Format
.venv\Scripts\ruff format .

# After changing a model, generate and apply a migration:
.venv\Scripts\alembic revision --autogenerate -m "describe the change"
.venv\Scripts\alembic upgrade head
```

### Project structure

```
app/
  api/           - FastAPI route handlers (one file per resource)
  cli.py         - `atm` command entry point
  core/
    config.py    - App settings (data dir, db URL)
    database.py  - SQLAlchemy engine and session
    schemas.py   - Pydantic request/response models
  models/
    models.py    - SQLAlchemy ORM models (Transaction, Category, Account, ImportBatch)
  services/
    csv_parser.py    - CSV column detection, date/amount parsing, row classification
    import_service.py - Commit parsed rows to the database
    mcc_map.py       - MCC description → category name mapping
  static/
    css/main.css - Global dark-theme styles
    js/api.js    - Frontend API wrapper
    js/utils.js  - Shared helpers (formatting, badges, alerts)
  templates/     - HTML pages (index, records, categories, dashboard)
  main.py        - FastAPI app, mounts static files, registers routers
migrations/      - Alembic migration scripts
pyproject.toml   - Dependencies, build config, Ruff settings
```

---

## Troubleshooting

**`atm` is not recognized after setup**
: Close and reopen your terminal. The PATH change only applies to new sessions.

**`atm` stops working after moving or recreating the project folder**
: The PATH entry points to `.venv\Scripts\` inside the project. Re-run the PATH setup step from the new location, then run `pip install -e .` again.

**Port 8000 is already in use**
: Run `atm --port 9000` (or any free port).

**Database is empty after switching machines**
: Copy `~/.brokeatm/brokeatm.db` from the old machine to the same path on the new one.

**Import fails with "Unrecognized CSV format"**
: Your CSV doesn't have a column that matches any known date or amount header. Open the file in a text editor, check the first row (the headers), and compare against the `FIELD_ALIASES` list in `app/services/csv_parser.py`. Add your bank's header names there.
