# AssessmentPortal

## Assessment Runtime Requirements

- The portal will run the Microsoft Zero Trust Assessment PowerShell module through a backend worker.
- DuckDB must not be installed or used anywhere in the runtime path.
- Assessment results must be persisted to Azure Database for PostgreSQL.
- The portal and worker will connect to Azure resources using managed identity.

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
