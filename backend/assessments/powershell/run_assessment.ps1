Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function ConvertTo-ZtCertificate {
    param(
        [Parameter(Mandatory = $true)]
        [string] $PfxBase64
    )

    $bytes = [Convert]::FromBase64String($PfxBase64)
    $flags = [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::EphemeralKeySet
    return [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($bytes, $null, $flags)
}

function Get-ZtManagedIdentityToken {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Resource
    )

    $encodedResource = [uri]::EscapeDataString($Resource)
    $managedIdentityClientId = $env:AZURE_CLIENT_ID

    if ($env:IDENTITY_ENDPOINT -and $env:IDENTITY_HEADER) {
        $uri = "$($env:IDENTITY_ENDPOINT)?api-version=2019-08-01&resource=$encodedResource"
        if ($managedIdentityClientId) {
            $uri = "$uri&client_id=$([uri]::EscapeDataString($managedIdentityClientId))"
        }

        $response = Invoke-RestMethod -Method GET -Uri $uri -Headers @{
            'X-IDENTITY-HEADER' = $env:IDENTITY_HEADER
        } -TimeoutSec 10 -ErrorAction Stop
        if (-not $response.access_token) {
            throw 'Managed identity token response did not include an access token.'
        }
        return $response.access_token
    }

    $uri = "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=$encodedResource"
    if ($managedIdentityClientId) {
        $uri = "$uri&client_id=$([uri]::EscapeDataString($managedIdentityClientId))"
    }

    $response = Invoke-RestMethod -Method GET -Uri $uri -Headers @{ Metadata = 'true' } -TimeoutSec 10 -ErrorAction Stop
    if (-not $response.access_token) {
        throw 'Managed identity token response did not include an access token.'
    }
    return $response.access_token
}

function Resolve-ZtKeyVaultSecretUri {
    param(
        [Parameter(Mandatory = $true)]
        [string] $CertificateUri
    )

    $parsedUri = [uri]$CertificateUri
    if ($parsedUri.Scheme -ne 'https' -or $parsedUri.Host -notlike '*.vault.azure.net') {
        throw 'ZTA_KEY_VAULT_CERTIFICATE_URI must be an Azure Key Vault HTTPS URI.'
    }

    $parts = $parsedUri.AbsolutePath.Trim('/').Split('/', [System.StringSplitOptions]::RemoveEmptyEntries)
    if ($parts.Count -lt 2 -or $parts[0] -notin @('certificates', 'secrets')) {
        throw 'ZTA_KEY_VAULT_CERTIFICATE_URI must target a Key Vault certificate or secret.'
    }

    $secretName = $parts[1]
    $secretVersion = if ($parts.Count -ge 3) { $parts[2] } else { $null }
    $vaultUrl = "$($parsedUri.Scheme)://$($parsedUri.Host)"

    if ($secretVersion) {
        return "$vaultUrl/secrets/$secretName/$secretVersion?api-version=7.5"
    }

    return "$vaultUrl/secrets/$secretName?api-version=7.5"
}

function Get-ZtCertificateFromKeyVault {
    param(
        [Parameter(Mandatory = $true)]
        [string] $CertificateUri
    )

    $token = Get-ZtManagedIdentityToken -Resource 'https://vault.azure.net'
    $secretUri = Resolve-ZtKeyVaultSecretUri -CertificateUri $CertificateUri
    $secret = Invoke-RestMethod -Method GET -Uri $secretUri -Headers @{
        Authorization = "Bearer $token"
    } -TimeoutSec 30 -ErrorAction Stop

    if (-not $secret.value) {
        throw 'Key Vault certificate secret did not contain a PFX value.'
    }

    return ConvertTo-ZtCertificate -PfxBase64 $secret.value
}

function Get-ZtInitialTenantDomain {
    $organization = Get-MgOrganization -Property VerifiedDomains | Select-Object -First 1
    if (-not $organization) {
        throw 'Unable to resolve tenant organization from Microsoft Graph.'
    }

    $initialDomain = @($organization.VerifiedDomains) | Where-Object { $_.IsInitial } | Select-Object -First 1
    if (-not $initialDomain -or -not $initialDomain.Name) {
        throw 'Unable to resolve the tenant initial domain from Microsoft Graph verified domains.'
    }

    return $initialDomain.Name.ToLowerInvariant()
}

function ConvertTo-ZtSharePointAdminUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string] $InitialDomain
    )

    if ($InitialDomain -notmatch '\.onmicrosoft\.com$') {
        throw "Cannot derive the SharePoint admin URL from initial domain '$InitialDomain'. Expected an onmicrosoft.com domain."
    }

    $tenantName = $InitialDomain -replace '\.onmicrosoft\.com$', ''
    return "https://$tenantName-admin.sharepoint.com"
}

$modulePath = $env:ZTA_MODULE_PATH
if (-not $modulePath) {
    throw 'ZTA_MODULE_PATH is required.'
}

$tenantId = $env:ZTA_TENANT_ID
$clientId = $env:ZTA_CLIENT_ID
$certificateUri = $env:ZTA_KEY_VAULT_CERTIFICATE_URI
$outputPath = $env:ZTA_OUTPUT_PATH
$pillar = if ($env:ZTA_PILLAR) { $env:ZTA_PILLAR } else { 'All' }
Import-Module (Join-Path $modulePath 'ZeroTrustAssessment.psd1') -Force

$certificate = Get-ZtCertificateFromKeyVault -CertificateUri $certificateUri

Connect-MgGraph -ClientId $clientId -TenantId $tenantId -Certificate $certificate -NoWelcome

$initialDomain = Get-ZtInitialTenantDomain
$sharePointAdminUrl = ConvertTo-ZtSharePointAdminUrl -InitialDomain $initialDomain

Connect-ExchangeOnline -AppID $clientId -Organization $initialDomain -Certificate $certificate -ShowBanner:$false
Connect-IPPSSession -AppID $clientId -Organization $initialDomain -Certificate $certificate
Connect-SPOService -Url $sharePointAdminUrl -ClientId $clientId -TenantId $tenantId -Certificate $certificate

Invoke-ZtAssessment -Path $outputPath -Pillar $pillar -DisableTelemetry
