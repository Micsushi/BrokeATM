# BrokeATM Deploy + Test TODO

This is the working checklist for getting BrokeATM onto Vercel + Supabase while
keeping the local downloadable version working.

## Current Target

- Local edition: FastAPI + SQLite, no auth, full CSV/PDF/OFX import support.
- Cloud edition: Vercel FastAPI + Supabase Auth + Supabase Postgres, CSV import only.
- Vercel entrypoint: `api/index.py`.
- Vercel config: `vercel.json`.
- Cloud requirements: `requirements.txt`.
- Supabase RLS setup: `supabase/brokeatm_cloud_schema.sql`.

References:
- Vercel FastAPI docs: https://vercel.com/docs/frameworks/backend/fastapi
- Vercel env vars: https://vercel.com/docs/environment-variables
- Supabase Postgres connections: https://supabase.com/docs/guides/database/connecting-to-postgres
- Supabase migrations: https://supabase.com/docs/guides/deployment/database-migrations

## What You Need To Provide

Access:
- GitHub repo access for the Vercel project.
- Vercel account/project access.
- Supabase project access.
- Permission to set Vercel environment variables.
- Permission to run SQL/migrations against Supabase Postgres.

Supabase values:
- `ATM_SUPABASE_URL`: Supabase Project URL.
- `ATM_SUPABASE_ANON_KEY`: Supabase anon/public key.
- `ATM_POSTGRES_URL`: Supabase Postgres connection URI.
- `ATM_SUPABASE_JWT_SECRET`: optional but recommended, used for local JWT validation.
- Supabase database password, needed to build the connection URI.

Vercel values:
- Production domain or preview URL.
- `ATM_SITE_URL`: final site URL, for auth redirects and app config.

Do not provide:
- Supabase `service_role` key for the public Vercel app unless a future server-only
  feature explicitly needs it. The current app does not require it.

## Recommended Supabase Connection

Use Supabase's Transaction Pooler URI for `ATM_POSTGRES_URL` because Vercel
Functions are temporary/serverless clients.

Supabase docs say:
- Direct connection: best for persistent servers.
- Session pooler: useful for persistent clients when direct IPv6 is unavailable.
- Transaction pooler: best for serverless/edge functions with transient connections.

The app normalizes these forms automatically:

```text
postgres://...
postgresql://...
```

to:

```text
postgresql+psycopg://...
```

## Local Test Checklist

Run from repo root in PowerShell.

1. Create/install the dev environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

2. Run full tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected current result:

```text
111 passed, 20 skipped
```

3. Run focused cloud/local deploy tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cloud_deployability.py tests\test_cloud_mode.py tests\test_self_deploy_local.py
```

Expected current result:

```text
17 passed
```

4. Run touched-file lint:

```powershell
.\.venv\Scripts\python.exe -m ruff check app\core\config.py app\core\database.py app\core\user_context.py app\main.py app\api\transactions_router.py app\api\recurring_router.py app\api\budget_router.py app\api\dashboard_router.py app\services\budget_service.py app\services\recurring_service.py migrations\versions\2f6d7c8e9a10_add_user_scope_columns.py tests\test_cloud_deployability.py tests\test_cloud_mode.py tests\test_self_deploy_local.py
```

Expected current result:

```text
All checks passed!
```

Note: broad `ruff check app tests migrations` currently reports pre-existing lint
debt outside the deploy changes. Treat that as a separate cleanup task.

5. Test a fresh SQLite migration path:

```powershell
$tempRoot = [System.IO.Path]::GetFullPath($env:TEMP)
$dir = Join-Path $tempRoot ("brokeatm-alembic-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $dir | Out-Null
$env:ATM_DATA_DIR = $dir
.\.venv\Scripts\python.exe -m alembic upgrade head
$code = $LASTEXITCODE
$fullDir = [System.IO.Path]::GetFullPath($dir)
if ($fullDir.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
  Remove-Item -LiteralPath $fullDir -Recurse -Force
}
exit $code
```

Expected result: exit code `0`.

6. Test local startup with an isolated data dir:

```powershell
$tempRoot = [System.IO.Path]::GetFullPath($env:TEMP)
$dir = Join-Path $tempRoot ("brokeatm-local-smoke-" + [guid]::NewGuid().ToString())
$env:ATM_DATA_DIR = $dir
$env:ATM_DEPLOYMENT_MODE = "local"
$env:ATM_AUTH_MODE = "none"
$env:ATM_DATABASE_BACKEND = "sqlite"
.\.venv\Scripts\python.exe -c "import app.main; from app.core.config import settings; print(app.main.app.title); print((settings.data_dir / 'brokeatm.db').exists())"
$code = $LASTEXITCODE
$fullDir = [System.IO.Path]::GetFullPath($dir)
if ($fullDir.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $fullDir)) {
  Remove-Item -LiteralPath $fullDir -Recurse -Force
}
exit $code
```

Expected output:

```text
BrokeATM
True
```

7. Test cloud import/cold-start shape without touching a real DB:

```powershell
$env:ATM_DEPLOYMENT_MODE = "cloud"
$env:ATM_AUTH_MODE = "supabase"
$env:ATM_DATABASE_BACKEND = "supabase_postgres"
$env:ATM_POSTGRES_URL = "postgresql://user:pass@localhost:5432/postgres"
$env:ATM_SUPABASE_URL = "https://example.supabase.co"
$env:ATM_SUPABASE_ANON_KEY = "anon-key"
.\.venv\Scripts\python.exe -c "from app.core.config import settings; from app.core.database import engine; import app.main; print(settings.database_url); print(engine.dialect.driver); print(app.main.app.title)"
```

Expected output includes:

```text
postgresql+psycopg://user:pass@localhost:5432/postgres
psycopg
BrokeATM
```

## Manual Local App Smoke

Run:

```powershell
$env:ATM_DEPLOYMENT_MODE = "local"
$env:ATM_AUTH_MODE = "none"
$env:ATM_DATABASE_BACKEND = "sqlite"
.\.venv\Scripts\atm --no-browser --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

Check:
- Dashboard loads.
- Settings API returns default currency.
- CSV import still works.
- PDF/OFX parser UI is still available locally.
- `/login` redirects to `/` in local no-auth mode.

## Windows Downloadable Smoke

Build:

```powershell
py -3.13 -m pip install -e ".[build]"
py -3.13 -m PyInstaller brokeatm.spec --clean --noconfirm
```

Run:

```powershell
.\dist\BrokeATM\BrokeATM.exe --no-browser --port 8767
```

Open:

```text
http://127.0.0.1:8767
```

Check:
- Home/dashboard loads.
- Settings API returns default currency.
- Local DB is created under `%USERPROFILE%\.brokeatm`.
- Local import features are still present.

Installer build:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 -Installer
```

Requires Inno Setup 6 on the build machine.

## Supabase Setup Checklist

1. Create a Supabase project.
2. Copy the Project URL and anon key.
3. Copy the Transaction Pooler connection URI from the Supabase Connect panel.
4. Put the connection URI in `ATM_POSTGRES_URL`.
5. Configure Supabase Auth:
   - Enable email/password.
   - Add the Vercel production URL to allowed redirect URLs.
   - Add preview URL patterns if you want preview deployments to support login.
6. Run BrokeATM Alembic migrations against the Supabase database.
7. Apply `supabase/brokeatm_cloud_schema.sql` after the core tables exist.

Important order:

```text
Alembic schema first
Supabase RLS SQL second
Vercel app deploy third
```

The RLS SQL intentionally fails fast if app tables or `user_id` columns are missing.

## Applying Database Schema

Option A: SQLAlchemy/Alembic direct from this repo.

```powershell
$env:ATM_DATABASE_BACKEND = "supabase_postgres"
$env:ATM_POSTGRES_URL = "<Supabase transaction pooler or direct migration URI>"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Then apply Supabase RLS SQL in Supabase SQL Editor or with `psql`:

```sql
-- contents of supabase/brokeatm_cloud_schema.sql
```

Option B: Supabase CLI workflow.

Use this only after converting/mirroring the Alembic schema into Supabase migration
files. Supabase's official flow is:

```powershell
supabase login
supabase link
supabase db push
```

Current repo note: this project already uses Alembic migrations under `migrations/`.
Do not assume `supabase db push` will apply those unless you add matching files under
`supabase/migrations/`.

## Vercel Environment Variables

Set these in Vercel Project Settings, for Production and any Preview environment you
want to test:

```text
ATM_DEPLOYMENT_MODE=cloud
ATM_AUTH_MODE=supabase
ATM_DATABASE_BACKEND=supabase_postgres
ATM_POSTGRES_URL=<Supabase Postgres transaction pooler URI>
ATM_SUPABASE_URL=<Supabase Project URL>
ATM_SUPABASE_ANON_KEY=<Supabase anon/public key>
ATM_SITE_URL=<https://your-vercel-domain>
ATM_SUPABASE_JWT_SECRET=<optional but recommended>
```

Do not set these for local downloadable builds unless you intentionally want to run
the cloud mode locally.

## Vercel Deploy Checklist

1. Connect the GitHub repo to Vercel.
2. Confirm Vercel sees `requirements.txt`.
3. Confirm `vercel.json` rewrites traffic to `/api/index`.
4. Set environment variables.
5. Deploy a Preview.
6. Open `/api/runtime/config` and confirm:

```json
{
  "deployment_mode": "cloud",
  "auth_mode": "supabase",
  "csv_only_imports": true
}
```

7. Open `/login`.
8. Create an account or sign in.
9. Confirm dashboard loads after sign-in.
10. Import a small CSV.
11. Confirm PDF/OFX import is blocked in cloud mode with a clear CSV-only message.
12. Promote to Production after the preview smoke passes.

## Cloud Smoke Checklist

Auth:
- `/login` loads.
- Sign-up sends confirmation when Supabase email confirmation is enabled.
- Sign-in works after confirmation.
- Sign-out returns to `/login`.
- Protected app pages redirect to `/login` when signed out.

Runtime:
- `/api/runtime/config` returns cloud mode.
- Static JS/CSS load correctly.
- `/api/settings` returns `CAD` for a new user.

Data isolation:
- User A categories/accounts/transactions are not visible to User B.
- User A cannot update a transaction with User B's category/account ID.
- Budget and recurring rule category/account IDs are owner-checked.

Import:
- CSV parse works.
- CSV duplicate check works.
- CSV commit writes rows for the signed-in user only.
- PDF/OFX parser endpoints return cloud CSV-only rejection.

Dashboard:
- Available months endpoint is scoped to the signed-in user.
- Dashboard totals match imported CSV rows.
- Budget page works for the signed-in user.
- Recurring rules create only user-owned transactions.

## Known Caveats

- Cloud V1 is CSV-only. Local keeps PDF/OCR/OFX support.
- Static assets are currently served by FastAPI. Vercel recommends `public/**` for CDN
  static assets. This can be optimized later.
- Broad Ruff lint has pre-existing debt. Full pytest is the stronger current safety
  gate until lint cleanup is scheduled.
- Real cloud deploy still needs a live Vercel/Supabase smoke with real credentials.

## Done Criteria

Local:
- Full pytest passes.
- Fresh SQLite Alembic upgrade passes.
- Local startup smoke passes.
- Windows executable smoke passes before publishing a downloadable release.

Cloud:
- Cloud import/cold-start smoke passes.
- Supabase Alembic migration succeeds.
- Supabase RLS SQL applies cleanly.
- Vercel preview deploy succeeds.
- Login + CSV import + dashboard smoke passes with a real Supabase user.
- Cross-user isolation spot check passes.
