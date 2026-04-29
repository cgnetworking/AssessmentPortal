# AssessmentPortal

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

## Tenant Authentication

Tenant assessment connections must use app-only certificate authentication only.

- Certificate private keys must be stored in Azure Key Vault.
- PostgreSQL must store certificate metadata only, such as tenant ID, client ID, thumbprint, and Key Vault certificate/secret URI.
- The worker must retrieve certificate material from Key Vault at run time using managed identity.
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
