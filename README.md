# AssessmentPortal

AssessmentPortal is a Django and React application for running Microsoft Zero Trust Assessment workflows, storing assessment history, and exposing results through a role-protected web portal.

Deployment instructions live in [deployment.md](deployment.md).

## Application Structure

- `backend/`: Django application, API, authentication, authorization, persistence, and assessment worker orchestration.
- `frontend/`: React/Vite browser application.
- `modules/ZeroTrustAssessment/`: forked Microsoft Zero Trust Assessment PowerShell module.
- `deploy/`: setup script, systemd units, Gunicorn config, Nginx config, and environment template.

## Architecture

The production app has four main runtime pieces:

- **Django API** stores tenant profiles, assessment runs, logs, results, report artifacts, and audit events.
- **React frontend** is built into static assets served by Nginx.
- **Assessment worker** runs queued assessments by launching the PowerShell Zero Trust Assessment module.
- **Azure Database for PostgreSQL** is the only supported persistent database.

Production deployment uses:

- Gunicorn as the local Django web server.
- Nginx as the public reverse proxy and static frontend server.
- A separate systemd worker process for queued assessments.
- Managed identity for Azure resource access.

## Key Decisions

- The target host platform is Ubuntu 24.04 or newer.
- PostgreSQL authentication uses Microsoft Entra managed identity only.
- Static PostgreSQL passwords, `DATABASE_URL`, and `ZT_POSTGRES_CONNECTION_STRING` are intentionally unsupported.
- The Django backend uses a custom PostgreSQL backend that injects a fresh managed identity token when opening database connections.
- The PowerShell assessment module uses the Ubuntu `psql` client for PostgreSQL access.
- The PowerShell database engine obtains the PostgreSQL managed identity token at `psql` launch time and exposes it as `PGPASSWORD` only for that child process.
- Tenant assessment authentication uses app-only certificate authentication.
- Certificate private keys must stay in Azure Key Vault. Django stores only certificate metadata and Key Vault URIs.
- The assessments UI can create a self-signed PFX certificate with the server's system-assigned managed identity, import it as a Key Vault certificate object in the vault configured by `ZTA_KEY_VAULT_URL`, and save the returned Key Vault certificate URI on the tenant profile. The Key Vault URL is environment-only configuration and is not set through the UI or tenant profile API.
- The assessment runner retrieves certificate material from Key Vault at run time with managed identity.
- Password, delegated user, interactive browser, device code, client secret, and local certificate-store authentication paths are not supported for tenant assessments.

## Data Model

The backend persists:

- Tenant profiles
- Assessment runs
- Run logs
- Assessment results
- Report artifacts stored in PostgreSQL
- Immutable audit events

Tenant profiles contain metadata required to run assessments, including tenant ID, app client ID, certificate thumbprint, and Key Vault certificate URI.

## Tenant Certificate Workflow

The portal can create a self-signed certificate for a tenant profile when `ZTA_KEY_VAULT_URL` is configured. The server imports the generated PFX as an exportable Key Vault certificate object and stores the returned certificate URI and thumbprint on the tenant profile.

The downloaded `.cer` file contains only the public certificate. Upload that `.cer` to the Microsoft Entra app registration identified by the tenant profile client ID before running assessments with the new certificate.

The portal host's managed identity needs `certificates/import` and `certificates/get` for certificate creation and public certificate download. The assessment runner also needs `secrets/get` to load the certificate object's backing PFX secret at runtime.

## Authorization

Users authenticate through Microsoft Entra ID and are authorized through Django groups.

Supported groups:

- `Portal Admin`
- `Assessment Operator`
- `Reader`

Role capabilities are defined in `backend/assessments/roles.py`. Superusers are treated as `Portal Admin`.

## Assessment Permissions

Every assessment connects to Microsoft Graph, Exchange Online, Security & Compliance PowerShell, and SharePoint Online. The runner derives the Exchange organization and SharePoint admin URL from the tenant's initial `onmicrosoft.com` domain after connecting to Microsoft Graph.

When the underlying Zero Trust Assessment module connects through Microsoft Graph PowerShell, the Graph PowerShell app requests consent for the permissions required by the assessment. The consent prompt is displayed only if the Graph PowerShell app does not already have the required permissions.

Required Microsoft Graph permissions:

- `AuditLog.Read.All`
- `CrossTenantInformation.ReadBasic.All`
- `DeviceManagementApps.Read.All`
- `DeviceManagementConfiguration.Read.All`
- `DeviceManagementManagedDevices.Read.All`
- `DeviceManagementRBAC.Read.All`
- `DeviceManagementServiceConfig.Read.All`
- `Directory.Read.All`
- `DirectoryRecommendations.Read.All`
- `EntitlementManagement.Read.All`
- `IdentityRiskEvent.Read.All`
- `IdentityRiskyUser.Read.All`
- `Policy.Read.All`
- `Policy.Read.ConditionalAccess`
- `Policy.Read.PermissionGrant`
- `PrivilegedAccess.Read.AzureAD`
- `Reports.Read.All`
- `RoleManagement.Read.All`
- `UserAuthenticationMethod.Read.All`
- `NetworkAccess.Read.All`
- `IdentityRiskyServicePrincipal.Read.All`

## API Surface

The Django API is mounted under `/api/`.

Primary endpoints:

- `GET /api/health/`
- `GET /api/auth/session/`
- `POST /api/auth/logout/`
- `GET /api/summary/`
- `GET /api/tenants/`
- `POST /api/tenants/`
- `GET /api/tenants/<tenant-id>/`
- `PATCH /api/tenants/<tenant-id>/`
- `DELETE /api/tenants/<tenant-id>/`
- `POST /api/tenants/<tenant-id>/certificate/`
- `GET /api/tenants/<tenant-id>/certificate/download/`
- `GET /api/runs/?tenantProfileId=<tenant-id>`
- `POST /api/runs/`
- `GET /api/runs/<run-id>/`
- `GET /api/runs/<run-id>/report/download/`
- `GET /api/audit-log/`

## Deployment

See [deployment.md](deployment.md) for operator setup steps, Azure prerequisites, environment configuration, service startup, verification, initial superuser creation, and first-login role assignment.
