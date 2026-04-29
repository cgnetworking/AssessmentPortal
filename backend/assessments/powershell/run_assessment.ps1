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
    $clientId = $env:AZURE_CLIENT_ID

    if ($env:IDENTITY_ENDPOINT -and $env:IDENTITY_HEADER) {
        $uri = "$($env:IDENTITY_ENDPOINT)?api-version=2019-08-01&resource=$encodedResource"
        if ($clientId) {
            $uri = "$uri&client_id=$([uri]::EscapeDataString($clientId))"
        }

        $response = Invoke-RestMethod -Method GET -Uri $uri -Headers @{
            'X-IDENTITY-HEADER' = $env:IDENTITY_HEADER
        }
        return $response.access_token
    }

    $uri = "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=$encodedResource"
    if ($clientId) {
        $uri = "$uri&client_id=$([uri]::EscapeDataString($clientId))"
    }

    $response = Invoke-RestMethod -Method GET -Uri $uri -Headers @{ Metadata = 'true' } -TimeoutSec 10
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
    }

    if (-not $secret.value) {
        throw 'Key Vault certificate secret did not contain a PFX value.'
    }

    return ConvertTo-ZtCertificate -PfxBase64 $secret.value
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

if (-not $env:ZTA_EXCHANGE_ORGANIZATION) {
    throw 'ZTA_EXCHANGE_ORGANIZATION is required because ExchangeOnline runs with every assessment.'
}

if (-not $env:ZTA_SHAREPOINT_ADMIN_URL) {
    throw 'ZTA_SHAREPOINT_ADMIN_URL is required because SharePointOnline runs with every assessment.'
}

Connect-MgGraph -ClientId $clientId -TenantId $tenantId -Certificate $certificate -NoWelcome
Connect-ExchangeOnline -AppID $clientId -Organization $env:ZTA_EXCHANGE_ORGANIZATION -Certificate $certificate -ShowBanner:$false
Connect-IPPSSession -AppID $clientId -Organization $env:ZTA_EXCHANGE_ORGANIZATION -Certificate $certificate
Connect-SPOService -Url $env:ZTA_SHAREPOINT_ADMIN_URL -ClientId $clientId -TenantId $tenantId -Certificate $certificate

Invoke-ZtAssessment -Path $outputPath -Pillar $pillar -DisableTelemetry
