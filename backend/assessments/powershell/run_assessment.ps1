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

$modulePath = $env:ZTA_MODULE_PATH
if (-not $modulePath) {
    throw 'ZTA_MODULE_PATH is required.'
}

$certificate = ConvertTo-ZtCertificate -PfxBase64 $env:ZTA_CERTIFICATE_PFX_BASE64
$tenantId = $env:ZTA_TENANT_ID
$clientId = $env:ZTA_CLIENT_ID
$outputPath = $env:ZTA_OUTPUT_PATH
$pillar = if ($env:ZTA_PILLAR) { $env:ZTA_PILLAR } else { 'All' }
$enabledConnectors = @()
if ($env:ZTA_ENABLED_CONNECTORS) {
    $enabledConnectors = ConvertFrom-Json -InputObject $env:ZTA_ENABLED_CONNECTORS
}

Import-Module (Join-Path $modulePath 'ZeroTrustAssessment.psd1') -Force

if ($enabledConnectors.Count -eq 0 -or $enabledConnectors -contains 'Graph') {
    Connect-MgGraph -ClientId $clientId -TenantId $tenantId -Certificate $certificate -NoWelcome
}

if (($enabledConnectors -contains 'ExchangeOnline') -and $env:ZTA_EXCHANGE_ORGANIZATION) {
    Connect-ExchangeOnline -AppID $clientId -Organization $env:ZTA_EXCHANGE_ORGANIZATION -Certificate $certificate -ShowBanner:$false
}

if (($enabledConnectors -contains 'SecurityCompliance') -and $env:ZTA_EXCHANGE_ORGANIZATION) {
    Connect-IPPSSession -AppID $clientId -Organization $env:ZTA_EXCHANGE_ORGANIZATION -Certificate $certificate
}

if (($enabledConnectors -contains 'SharePointOnline') -and $env:ZTA_SHAREPOINT_ADMIN_URL) {
    Connect-SPOService -Url $env:ZTA_SHAREPOINT_ADMIN_URL -ClientId $clientId -TenantId $tenantId -Certificate $certificate
}

Invoke-ZtAssessment -Path $outputPath -Pillar $pillar -DisableTelemetry
