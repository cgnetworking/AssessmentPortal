#Requires -Modules Az.Accounts, Az.Resources, Az.Network, Az.KeyVault, Az.PrivateDns

[CmdletBinding()]
param(
    [string] $SubscriptionId,

    [Parameter(Mandatory)]
    [string] $ResourceGroupName,

    [string] $Location = "eastus",
    [string] $NamePrefix = "assessmentportal",
    [string] $VNetName = "vnet-assessmentportal",
    [string] $PostgresServerName,
    [string] $KeyVaultName,

    [Parameter(Mandatory)]
    [securestring] $PostgresAdminPassword
)

$ErrorActionPreference = "Stop"

if ($SubscriptionId) {
    Set-AzContext -SubscriptionId $SubscriptionId | Out-Null
}

$context = Get-AzContext
if (-not $context) {
    throw "Run Connect-AzAccount before this script."
}

$suffix = Get-Random -Minimum 10000 -Maximum 99999
if (-not $PostgresServerName) {
    $PostgresServerName = "$NamePrefix-pg-$suffix".ToLowerInvariant()
}
if (-not $KeyVaultName) {
    $KeyVaultName = "$($NamePrefix -replace '[^a-zA-Z0-9]', '')kv$suffix".ToLowerInvariant()
    if ($KeyVaultName.Length -gt 24) {
        $KeyVaultName = $KeyVaultName.Substring(0, 24)
    }
}

$tags = @{
    application = "AssessmentPortal"
    environment = "dev-test"
    redundancy = "none"
}

New-AzResourceGroup `
    -Name $ResourceGroupName `
    -Location $Location `
    -Tag $tags `
    -Force | Out-Null

$appSubnet = New-AzVirtualNetworkSubnetConfig `
    -Name "snet-app" `
    -AddressPrefix "10.0.0.0/26"

$postgresSubnet = New-AzVirtualNetworkSubnetConfig `
    -Name "snet-postgres-pe" `
    -AddressPrefix "10.0.0.64/26" `
    -PrivateEndpointNetworkPoliciesFlag Disabled

$keyVaultSubnet = New-AzVirtualNetworkSubnetConfig `
    -Name "snet-keyvault-pe" `
    -AddressPrefix "10.0.0.128/26" `
    -PrivateEndpointNetworkPoliciesFlag Disabled

$reservedSubnet = New-AzVirtualNetworkSubnetConfig `
    -Name "snet-reserved" `
    -AddressPrefix "10.0.0.192/26"

$vnet = New-AzVirtualNetwork `
    -Name $VNetName `
    -ResourceGroupName $ResourceGroupName `
    -Location $Location `
    -AddressPrefix "10.0.0.0/24" `
    -Subnet $appSubnet, $postgresSubnet, $keyVaultSubnet, $reservedSubnet `
    -Tag $tags

$postgresTemplate = @{
    '$schema' = "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
    contentVersion = "1.0.0.0"
    parameters = @{
        serverName = @{ type = "string" }
        adminPassword = @{ type = "secureString" }
        tenantId = @{ type = "string" }
    }
    resources = @(
        @{
            type = "Microsoft.DBforPostgreSQL/flexibleServers"
            apiVersion = "2024-08-01"
            name = "[parameters('serverName')]"
            location = $Location
            tags = $tags
            sku = @{
                name = "Standard_B1ms"
                tier = "Burstable"
            }
            properties = @{
                version = "16"
                administratorLogin = "pgadmin"
                administratorLoginPassword = "[parameters('adminPassword')]"
                authConfig = @{
                    activeDirectoryAuth = "Enabled"
                    passwordAuth = "Enabled"
                    tenantId = "[parameters('tenantId')]"
                }
                backup = @{
                    backupRetentionDays = 7
                    geoRedundantBackup = "Disabled"
                }
                highAvailability = @{
                    mode = "Disabled"
                }
                network = @{
                    publicNetworkAccess = "Disabled"
                }
                storage = @{
                    autoGrow = "Disabled"
                    storageSizeGB = 32
                }
            }
        }
        @{
            type = "Microsoft.DBforPostgreSQL/flexibleServers/databases"
            apiVersion = "2024-08-01"
            name = "[format('{0}/assessment_portal', parameters('serverName'))]"
            dependsOn = @(
                "[resourceId('Microsoft.DBforPostgreSQL/flexibleServers', parameters('serverName'))]"
            )
            properties = @{
                charset = "UTF8"
                collation = "en_US.utf8"
            }
        }
    )
}

New-AzResourceGroupDeployment `
    -Name "postgres-$suffix" `
    -ResourceGroupName $ResourceGroupName `
    -TemplateObject $postgresTemplate `
    -serverName $PostgresServerName `
    -adminPassword $PostgresAdminPassword `
    -tenantId $context.Tenant.Id | Out-Null

$postgres = Get-AzResource `
    -ResourceGroupName $ResourceGroupName `
    -ResourceType "Microsoft.DBforPostgreSQL/flexibleServers" `
    -Name $PostgresServerName

$vault = New-AzKeyVault `
    -Name $KeyVaultName `
    -ResourceGroupName $ResourceGroupName `
    -Location $Location `
    -Sku Standard `
    -PublicNetworkAccess Disabled `
    -SoftDeleteRetentionInDays 7 `
    -Tag $tags

$postgresDnsZone = New-AzPrivateDnsZone `
    -ResourceGroupName $ResourceGroupName `
    -Name "privatelink.postgres.database.azure.com" `
    -Tag $tags

New-AzPrivateDnsVirtualNetworkLink `
    -ResourceGroupName $ResourceGroupName `
    -ZoneName $postgresDnsZone.Name `
    -Name "link-postgres" `
    -VirtualNetworkId $vnet.Id `
    -Tag $tags | Out-Null

$keyVaultDnsZone = New-AzPrivateDnsZone `
    -ResourceGroupName $ResourceGroupName `
    -Name "privatelink.vaultcore.azure.net" `
    -Tag $tags

New-AzPrivateDnsVirtualNetworkLink `
    -ResourceGroupName $ResourceGroupName `
    -ZoneName $keyVaultDnsZone.Name `
    -Name "link-keyvault" `
    -VirtualNetworkId $vnet.Id `
    -Tag $tags | Out-Null

$postgresPeConnection = New-AzPrivateLinkServiceConnection `
    -Name "psc-postgres" `
    -PrivateLinkServiceId $postgres.ResourceId `
    -GroupId "postgresqlServer"

$postgresPe = New-AzPrivateEndpoint `
    -Name "pe-postgres" `
    -ResourceGroupName $ResourceGroupName `
    -Location $Location `
    -Subnet ($vnet.Subnets | Where-Object Name -eq "snet-postgres-pe") `
    -PrivateLinkServiceConnection $postgresPeConnection `
    -Tag $tags `
    -Force

$postgresDnsConfig = New-AzPrivateDnsZoneConfig `
    -Name "postgres" `
    -PrivateDnsZoneId $postgresDnsZone.ResourceId

New-AzPrivateDnsZoneGroup `
    -ResourceGroupName $ResourceGroupName `
    -PrivateEndpointName $postgresPe.Name `
    -Name "default" `
    -PrivateDnsZoneConfig $postgresDnsConfig `
    -Force | Out-Null

$keyVaultPeConnection = New-AzPrivateLinkServiceConnection `
    -Name "psc-keyvault" `
    -PrivateLinkServiceId $vault.ResourceId `
    -GroupId "vault"

$keyVaultPe = New-AzPrivateEndpoint `
    -Name "pe-keyvault" `
    -ResourceGroupName $ResourceGroupName `
    -Location $Location `
    -Subnet ($vnet.Subnets | Where-Object Name -eq "snet-keyvault-pe") `
    -PrivateLinkServiceConnection $keyVaultPeConnection `
    -Tag $tags `
    -Force

$keyVaultDnsConfig = New-AzPrivateDnsZoneConfig `
    -Name "keyvault" `
    -PrivateDnsZoneId $keyVaultDnsZone.ResourceId

New-AzPrivateDnsZoneGroup `
    -ResourceGroupName $ResourceGroupName `
    -PrivateEndpointName $keyVaultPe.Name `
    -Name "default" `
    -PrivateDnsZoneConfig $keyVaultDnsConfig `
    -Force | Out-Null

[pscustomobject]@{
    ResourceGroupName = $ResourceGroupName
    VNetName = $VNetName
    PostgresServerName = $PostgresServerName
    PostgresHost = "$PostgresServerName.postgres.database.azure.com"
    PostgresDatabase = "assessment_portal"
    KeyVaultName = $KeyVaultName
    KeyVaultUri = $vault.VaultUri
}
