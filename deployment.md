# Deployment

This guide covers the actions an operator must perform to deploy AssessmentPortal on Ubuntu 24.04 or newer.

## 1. Prepare Azure

Create or identify these Azure resources before running the app:

- Azure Database for PostgreSQL with Microsoft Entra authentication enabled.
- A PostgreSQL database role mapped to the portal host's system-assigned managed identity.
- Azure Key Vault containing the certificate objects used for tenant assessments.
- The portal host's system-assigned managed identity with access to Azure Database for PostgreSQL and the required Key Vault certificate objects and backing certificate secrets.
- A Microsoft Entra app registration for portal login.

Configure the Microsoft Entra app registration redirect URI:

```text
https://<host>/auth/complete/azuread-tenant-oauth2/
```

The portal backend, database token flow, and Key Vault certificate actions use the host's system-assigned managed identity.

Create the PostgreSQL role for the portal host's managed identity before running Django migrations. Connect to the `postgres` database as a Microsoft Entra PostgreSQL administrator and run:

```sql
select * from pg_catalog.pgaadauth_create_principal('<managed-identity-resource-name>', false, false);
```

Then connect to the application database and grant the role permission to create and use objects in the `public` schema:

```sql
GRANT CONNECT ON DATABASE assessment_portal TO "<managed-identity-resource-name>";
GRANT USAGE, CREATE ON SCHEMA public TO "<managed-identity-resource-name>";
ALTER ROLE "<managed-identity-resource-name>" IN DATABASE assessment_portal SET search_path TO public;
```

Set `POSTGRES_USER` in `/etc/assessmentportal/assessmentportal.env` to the same managed identity resource name used for the PostgreSQL role. If tables were created earlier by a different owner, also grant access to those existing objects from the application database:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "<managed-identity-resource-name>";
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO "<managed-identity-resource-name>";
```

## 2. Prepare The Host

Use an Ubuntu 24.04 or newer host.

Make sure the host has:

- Network access to Azure Database for PostgreSQL.
- Network access to Azure Key Vault.
- A DNS name that points to the host.
- TLS certificate files at `/etc/letsencrypt/live/<host>/fullchain.pem` and `/etc/letsencrypt/live/<host>/privkey.pem`, or use the setup script's `--self-signed-cert` option for non-production deployments.
- A checkout of this repository.

## 3. Run The Setup Script

From the repository root, run:

```bash
sudo deploy/scripts/setup_ubuntu.sh --domain <host>
```

For non-production or private deployments without a trusted certificate, run:

```bash
sudo deploy/scripts/setup_ubuntu.sh --domain <host> --self-signed-cert
```

The script installs operating system packages, PowerShell, Python dependencies, frontend dependencies, systemd units, and the Nginx site config. It creates `/etc/assessmentportal/assessmentportal.env` if it does not already exist.

If the environment file still contains placeholder values, the script leaves services stopped.

## 4. Configure The Environment

Edit the generated environment file:

```bash
sudo nano /etc/assessmentportal/assessmentportal.env
```

Set these values:

- `DJANGO_SECRET_KEY`, at least 50 characters
- `DJANGO_ALLOWED_HOSTS`
- `FRONTEND_URL`
- `CSRF_TRUSTED_ORIGINS`
- `POSTGRES_HOST`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PORT`
- `POSTGRES_SSLMODE`
- `AZUREAD_AUTH_CLIENT_ID`
- `AZUREAD_AUTH_CLIENT_SECRET`
- `AZUREAD_AUTH_TENANT_ID`
- `ZTA_KEY_VAULT_URL`

## 5. Start Services

After replacing placeholder environment values, start the app:

```bash
sudo /opt/assessmentportal/deploy/scripts/restart_services.sh
```

If the setup script stopped before starting services because placeholders were present, you can also rerun the setup script without repeating Node.js, PowerShell, or frontend work:

```bash
sudo /opt/assessmentportal/deploy/scripts/setup_ubuntu.sh --domain <host> --skip-node-install --skip-powershell-install --skip-frontend-build
```

## 6. Verify The Deployment

Check service status:

```bash
sudo systemctl status assessmentportal-gunicorn assessmentportal-worker
```

Check that unauthenticated requests are challenged:

```bash
curl -i https://<host>/api/health/
```

The expected response before sign-in is `401 Unauthorized`. Browser requests to the portal pages should show the portal sign-in screen before any application chrome or data is displayed.

Open the portal:

```text
https://<host>/
```

## 7. Create The Initial Superuser

Create one local Django superuser before assigning application roles. This account is used to sign in to Django admin at `https://<host>/admin/`; normal portal users still authenticate through Microsoft Entra ID.

Run this after migrations have completed:

```bash
sudo /opt/assessmentportal/deploy/scripts/manage.sh createsuperuser
```

The wrapper loads `/etc/assessmentportal/assessmentportal.env`, changes into the deployed backend directory, and runs the command with the deployment virtual environment as the `assessmentportal` user. Running raw `python manage.py createsuperuser` without loading that environment will fail with errors such as `DJANGO_SECRET_KEY is required`.

The superuser is treated as `Portal Admin` by the application.

## 8. Assign Application Roles

After users sign in for the first time, assign them to one of these Django groups through Django admin:

- `Portal Admin`
- `Assessment Operator`
- `Reader`

The groups are created by Django migration, but user membership is manual.
