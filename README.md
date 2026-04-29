# AssessmentPortal

## Application Structure

- `backend/`: Django app and JSON API.
- `frontend/`: React/Vite frontend.
- `modules/ZeroTrustAssessment/`: forked Microsoft Zero Trust Assessment PowerShell module.

## Assessment Runtime Requirements

- The application and assessment worker will run only on Ubuntu 24.04 or newer.
- The portal will run the Microsoft Zero Trust Assessment PowerShell module through a backend worker.
- DuckDB must not be installed or used anywhere in the runtime path.
- The forked module lives under `modules/ZeroTrustAssessment`.
- The forked module must not bundle or load DuckDB native libraries or require the Microsoft Visual C++ Redistributable.
- The forked module uses PostgreSQL through the Ubuntu `psql` client and standard PostgreSQL environment variables.
- Assessment results must be persisted to Azure Database for PostgreSQL.
- The portal and worker will connect to Azure resources using managed identity.

## PostgreSQL Runtime

The worker must provide PostgreSQL connectivity before invoking the module:

- `ZT_POSTGRES_CONNECTION_STRING` or `DATABASE_URL`, or standard `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, and related `PG*` variables.
- `ZT_POSTGRES_SCHEMA` may be set to isolate an assessment run; otherwise the module uses the `main` schema.
- For Azure Database for PostgreSQL with managed identity, the worker is responsible for acquiring the Entra access token and passing it as the PostgreSQL password.

## Django Backend

The backend stores tenant profiles, assessment runs, run logs, results, and report artifacts in PostgreSQL.

Required environment variables:

- `POSTGRES_HOST`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_PORT`, defaults to `5432`
- `POSTGRES_SSLMODE`, defaults to `require`
- `AZUREAD_AUTH_CLIENT_ID`
- `AZUREAD_AUTH_CLIENT_SECRET`
- `AZUREAD_AUTH_TENANT_ID`
- `FRONTEND_URL`, defaults to `http://127.0.0.1:5173`
- `CSRF_TRUSTED_ORIGINS`, defaults to `http://127.0.0.1:5173,http://localhost:5173`

The Microsoft Entra app registration redirect URI must point to the Django social-auth callback:

```text
https://<backend-host>/auth/complete/azuread-tenant-oauth2/
```

## Application Roles

Users authenticate through Microsoft Entra ID, then must be manually assigned to one of these Django groups in the application after their first login:

- `Portal Admin`
- `Assessment Operator`
- `Reader`

Role permissions:

- `Portal Admin`: manage tenant profiles, configure Key Vault certificate references, delete tenants, run assessments, and view all results/logs.
- `Assessment Operator`: view tenant profiles, run assessments, and view results/logs. Operators cannot edit certificate or tenant settings and cannot delete tenants.
- `Reader`: view tenant profiles, run history, logs, and reports only.

The groups are created by Django migration. Assign users through Django admin after they first sign in and their user record exists.

Run locally after installing dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd backend
python manage.py migrate
python manage.py runserver
```

Run a queued assessment:

```bash
cd backend
python manage.py run_assessment <assessment-run-id>
```

Run the worker loop:

```bash
cd backend
python manage.py run_queued_assessments
```

The assessment worker expects `pwsh`, `psql`, the required Microsoft PowerShell service modules, and managed identity access to Key Vault and Azure Database for PostgreSQL.

## React Frontend

Run the frontend in a separate shell:

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api` requests to `http://127.0.0.1:8000`.

## Production Runtime

Production deployment uses:

- Gunicorn as the local Django web server.
- Nginx as the public reverse proxy.
- Nginx serves the React build from `frontend/dist`.
- Nginx proxies `/api/`, `/auth/`, and `/admin/` to Gunicorn through a Unix socket.
- A separate systemd worker runs queued assessments.

Deployment assets are in `deploy/`:

- `deploy/gunicorn/assessment_portal.py`
- `deploy/nginx/assessmentportal.conf`
- `deploy/systemd/assessmentportal-gunicorn.service`
- `deploy/systemd/assessmentportal-worker.service`
- `deploy/env/assessmentportal.env.example`

See `deploy/README.md` for the Ubuntu 24.04+ setup flow.

## API Endpoints

- `GET /api/health/`
- `GET /api/auth/session/`
- `POST /api/auth/logout/`
- `GET /api/summary/`
- `GET /api/tenants/`
- `POST /api/tenants/`
- `GET /api/tenants/<tenant-id>/`
- `PATCH /api/tenants/<tenant-id>/`
- `DELETE /api/tenants/<tenant-id>/`
- `GET /api/runs/?tenantProfileId=<tenant-id>`
- `POST /api/runs/`
- `GET /api/runs/<run-id>/`

## Tenant Authentication

Tenant assessment connections must use app-only certificate authentication only.

- Certificate private keys must be stored in Azure Key Vault.
- PostgreSQL must store certificate metadata only, such as tenant ID, client ID, thumbprint, and Key Vault certificate/secret URI.
- The PowerShell runner must retrieve certificate material from Key Vault at run time using managed identity. Django passes only the Key Vault certificate/secret URI to the runner, not the PFX/private key material.
- The preferred connector pattern is an in-memory `X509Certificate2` object passed with `-Certificate`.
- Do not add password, delegated user, interactive browser, device code, client secret, or locally installed certificate-store auth paths.
- Use certificate file paths or thumbprint auth only if a connector does not support in-memory certificate objects and the fallback is explicitly approved.

The assessment connector bootstrap should use this pattern wherever supported:

```powershell
Connect-MgGraph -ClientId $ClientId -TenantId $TenantId -Certificate $Certificate
Connect-ExchangeOnline -AppID $ClientId -Organization $Organization -Certificate $Certificate
Connect-IPPSSession -AppID $ClientId -Organization $Organization -Certificate $Certificate
Connect-SPOService -Url $AdminUrl -ClientId $ClientId -TenantId $TenantId -Certificate $Certificate
```
