Set-StrictMode -Off
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

function Add-ZtUriQueryParameter {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Uri,

        [Parameter(Mandatory = $true)]
        [hashtable] $Query
    )

    $builder = [System.UriBuilder]::new($Uri)
    $queryParameters = [ordered]@{}
    if ($builder.Query) {
        foreach ($pair in $builder.Query.TrimStart('?').Split('&', [System.StringSplitOptions]::RemoveEmptyEntries)) {
            $parts = $pair.Split('=', 2)
            $key = [uri]::UnescapeDataString($parts[0])
            $value = if ($parts.Count -gt 1) { [uri]::UnescapeDataString($parts[1]) } else { '' }
            $queryParameters[$key] = $value
        }
    }

    foreach ($key in $Query.Keys) {
        if ($null -ne $Query[$key] -and $Query[$key] -ne '') {
            $queryParameters[$key] = [string]$Query[$key]
        }
    }

    $encodedQuery = foreach ($key in $queryParameters.Keys) {
        '{0}={1}' -f [uri]::EscapeDataString($key), [uri]::EscapeDataString($queryParameters[$key])
    }
    $builder.Query = $encodedQuery -join '&'
    return $builder.Uri.AbsoluteUri
}

function Get-ZtManagedIdentityToken {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Resource
    )

    $managedIdentityClientId = $env:AZURE_CLIENT_ID

    if ($env:IDENTITY_ENDPOINT -and $env:IDENTITY_HEADER) {
        $query = @{
            'api-version' = '2019-08-01'
            resource = $Resource
        }
        if ($managedIdentityClientId) {
            $query['client_id'] = $managedIdentityClientId
        }
        $uri = Add-ZtUriQueryParameter -Uri $env:IDENTITY_ENDPOINT -Query $query

        try {
            $response = Invoke-RestMethod -Method GET -Uri $uri -Headers @{
                'X-IDENTITY-HEADER' = $env:IDENTITY_HEADER
            } -TimeoutSec 10 -ErrorAction Stop
        }
        catch {
            throw "Managed identity token request failed for resource '$Resource' using IDENTITY_ENDPOINT. $($_.Exception.Message)"
        }
        if (-not $response.access_token) {
            throw 'Managed identity token response did not include an access token.'
        }
        return $response.access_token
    }

    $query = @{
        'api-version' = '2018-02-01'
        resource = $Resource
    }
    if ($managedIdentityClientId) {
        $query['client_id'] = $managedIdentityClientId
    }
    $uri = Add-ZtUriQueryParameter -Uri 'http://169.254.169.254/metadata/identity/oauth2/token' -Query $query

    try {
        $response = Invoke-RestMethod -Method GET -Uri $uri -Headers @{ Metadata = 'true' } -TimeoutSec 10 -ErrorAction Stop
    }
    catch {
        throw "Managed identity token request failed for resource '$Resource' using IMDS. $($_.Exception.Message)"
    }
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
        return Add-ZtUriQueryParameter -Uri "$vaultUrl/secrets/$secretName/$secretVersion" -Query @{ 'api-version' = '7.5' }
    }

    return Add-ZtUriQueryParameter -Uri "$vaultUrl/secrets/$secretName" -Query @{ 'api-version' = '7.5' }
}

function Get-ZtCertificateFromKeyVault {
    param(
        [Parameter(Mandatory = $true)]
        [string] $CertificateUri
    )

    $token = Get-ZtManagedIdentityToken -Resource 'https://vault.azure.net'
    $secretUri = Resolve-ZtKeyVaultSecretUri -CertificateUri $CertificateUri
    try {
        $secret = Invoke-RestMethod -Method GET -Uri $secretUri -Headers @{
            Authorization = "Bearer $token"
        } -TimeoutSec 30 -ErrorAction Stop
    }
    catch {
        throw "Key Vault certificate secret request failed. $($_.Exception.Message)"
    }

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

function Add-ZtRequiredModulesPath {
    $requiredModulesPath = $env:ZTA_REQUIRED_MODULES_PATH
    if (-not $requiredModulesPath) {
        if (-not $env:HOME) {
            return
        }
        $requiredModulesPath = Join-Path $env:HOME '.cache/ZeroTrustAssessment/Modules'
    }

    $separator = [System.IO.Path]::PathSeparator
    $modulePath = @($env:PSModulePath -split $separator | Where-Object { $_ })
    $normalizedModulePath = $modulePath | ForEach-Object { $_.TrimEnd([System.IO.Path]::DirectorySeparatorChar) }
    if ($requiredModulesPath.TrimEnd([System.IO.Path]::DirectorySeparatorChar) -notin $normalizedModulePath) {
        $env:PSModulePath = (@($requiredModulesPath) + $modulePath) -join $separator
    }
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
Add-ZtRequiredModulesPath
Import-Module (Join-Path $modulePath 'ZeroTrustAssessment.psd1') -Force

$certificate = Get-ZtCertificateFromKeyVault -CertificateUri $certificateUri

Connect-MgGraph -ClientId $clientId -TenantId $tenantId -Certificate $certificate -NoWelcome

$initialDomain = Get-ZtInitialTenantDomain
$sharePointAdminUrl = ConvertTo-ZtSharePointAdminUrl -InitialDomain $initialDomain

Connect-ExchangeOnline -AppID $clientId -Organization $initialDomain -Certificate $certificate -ShowBanner:$false
Connect-IPPSSession -AppID $clientId -Organization $initialDomain -Certificate $certificate
Connect-SPOService -Url $sharePointAdminUrl -ClientId $clientId -TenantId $tenantId -Certificate $certificate

Invoke-ZtAssessment -Path $outputPath -Pillar $pillar -DisableTelemetry
