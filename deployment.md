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
- Key Vault certificate URI

To create certificates from the portal UI, set `ZTA_KEY_VAULT_URL` to the target vault URL, such as `https://example.vault.azure.net`. The Key Vault URL is environment-only configuration and cannot be set from the UI or tenant profile API. The Linux server uses its system-assigned managed identity to create a self-signed PFX certificate, imports it as an exportable Key Vault certificate object in the configured vault, and saves the resulting certificate URI and thumbprint on the tenant profile. The managed identity needs `certificates/import` and `certificates/get` for the portal action, and `secrets/get` for the assessment runner to load the certificate object's backing PFX secret at runtime.

The public `.cer` download contains only the public certificate. Upload that `.cer` to the Microsoft Entra app registration identified by the tenant profile Client ID before running assessments with the new certificate.

Do not use password, delegated user, interactive browser, device code, client secret, or locally installed certificate-store authentication paths for tenant assessments.
