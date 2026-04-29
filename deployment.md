# Deployment

This guide covers the actions an operator must perform to deploy AssessmentPortal on Ubuntu 24.04 or newer.

## 1. Prepare Azure

Create or identify these Azure resources before running the app:

- Azure Database for PostgreSQL with Microsoft Entra authentication enabled.
- A PostgreSQL database role mapped to the portal managed identity.
- Azure Key Vault containing the certificate secrets used for tenant assessments.
- A managed identity with access to Azure Database for PostgreSQL and the required Key Vault certificate secrets.
- A Microsoft Entra app registration for portal login.

Configure the Microsoft Entra app registration redirect URI:

```text
https://<host>/auth/complete/azuread-tenant-oauth2/
```

If you use a user-assigned managed identity, note its client ID. If you use a system-assigned managed identity, leave `AZURE_CLIENT_ID` empty in the app environment file.

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

- `DJANGO_SECRET_KEY`
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
- `AZURE_CLIENT_ID`, only for user-assigned managed identity

Do not configure these values:

- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `ZT_POSTGRES_CONNECTION_STRING`

## 5. Start Services

After replacing placeholder environment values, start the app:

```bash
sudo systemctl restart assessmentportal-gunicorn assessmentportal-worker
sudo nginx -t
sudo systemctl reload nginx
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

Check the health endpoint:

```bash
curl -fsS https://<host>/api/health/
```

Open the portal:

```text
https://<host>/
```

## 7. Assign Application Roles

After users sign in for the first time, assign them to one of these Django groups through Django admin:

- `Portal Admin`
- `Assessment Operator`
- `Reader`

The groups are created by Django migration, but user membership is manual.

## 8. Add Tenant Profiles

For each tenant assessment profile, use app-only certificate authentication.

Certificate private keys must remain in Azure Key Vault. Store only certificate metadata in the portal, such as:

- Tenant ID
- Client ID
- Certificate thumbprint
- Key Vault certificate or secret URI

Do not use password, delegated user, interactive browser, device code, client secret, or locally installed certificate-store authentication paths for tenant assessments.
