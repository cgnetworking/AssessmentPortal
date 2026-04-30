#Requires -Modules Az.Accounts, Az.Resources, Az.Network, Az.KeyVault, Az.PrivateDns

[CmdletBinding()]
param(
    [string] $SubscriptionId,

    [Parameter(Mandatory)]
    [string] $ResourceGroupName,

    [string] $Location = "eastus",
    [string] $NamePrefix = "assessmentportal",
    [string] $VNetName = "vnet-assessmentportal",
    [string] $VNetAddressPrefix = "10.0.0.0/24",

    [string] $AppSubnetName = "snet-app",
    [string] $AppSubnetPrefix = "10.0.0.0/26",

    [string] $PostgresSubnetName = "snet-postgres-pe",
    [string] $PostgresSubnetPrefix = "10.0.0.64/26",

    [string] $KeyVaultSubnetName = "snet-keyvault-pe",
    [string] $KeyVaultSubnetPrefix = "10.0.0.128/26",

    [string] $ReservedSubnetName = "snet-reserved",
    [string] $ReservedSubnetPrefix = "10.0.0.192/26",

    [string] $PostgresServerName,
    [string] $PostgresDatabaseName = "assessment_portal",
    [string] $PostgresVersion = "16",
    [string] $PostgresSkuName = "Standard_B1ms",
    [string] $PostgresSkuTier = "Burstable",
    [int] $PostgresStorageSizeGB = 32,
    [int] $PostgresBackupRetentionDays = 7,
    [string] $PostgresActiveDirectoryAuth = "Enabled",
    [string] $PostgresPasswordAuth = "Disabled",
    [string] $PostgresPublicNetworkAccess = "Disabled",
    [string] $PostgresGeoRedundantBackup = "Disabled",
    [string] $PostgresHighAvailabilityMode = "Disabled",
    [string] $PostgresStorageAutoGrow = "Disabled",
    [string] $PostgresDatabaseCharset = "UTF8",
    [string] $PostgresDatabaseCollation = "en_US.utf8",

    [Parameter(Mandatory)]
    [string] $PostgresEntraAdminObjectId,

    [Parameter(Mandatory)]
    [string] $PostgresEntraAdminName,

    [string] $PostgresEntraAdminType = "Group",

    [string] $KeyVaultName,
    [string] $KeyVaultSku = "Standard",
    [string] $KeyVaultPublicNetworkAccess = "Disabled",
    [int] $KeyVaultSoftDeleteRetentionDays = 7,

    [string] $PostgresPrivateDnsZoneName = "privatelink.postgres.database.azure.com",
    [string] $KeyVaultPrivateDnsZoneName = "privatelink.vaultcore.azure.net",
    [string] $PostgresPrivateDnsLinkName = "link-postgres",
    [string] $KeyVaultPrivateDnsLinkName = "link-keyvault",
    [string] $PrivateDnsZoneGroupName = "default",

    [string] $PostgresPrivateEndpointName = "pe-postgres",
    [string] $KeyVaultPrivateEndpointName = "pe-keyvault",
    [string] $PostgresPrivateEndpointConnectionName = "psc-postgres",
    [string] $KeyVaultPrivateEndpointConnectionName = "psc-keyvault",
    [string] $PostgresPrivateEndpointGroupId = "postgresqlServer",
    [string] $KeyVaultPrivateEndpointGroupId = "vault",
    [string] $PostgresPrivateDnsConfigName = "postgres",
    [string] $KeyVaultPrivateDnsConfigName = "keyvault",

    [hashtable] $Tags = @{
        application = "AssessmentPortal"
        environment = "dev-test"
        redundancy = "none"
    }
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

New-AzResourceGroup `
    -Name $ResourceGroupName `
    -Location $Location `
    -Tag $Tags `
    -Force | Out-Null

$appSubnet = New-AzVirtualNetworkSubnetConfig `
    -Name $AppSubnetName `
    -AddressPrefix $AppSubnetPrefix

$postgresSubnet = New-AzVirtualNetworkSubnetConfig `
    -Name $PostgresSubnetName `
    -AddressPrefix $PostgresSubnetPrefix `
    -PrivateEndpointNetworkPoliciesFlag Disabled

$keyVaultSubnet = New-AzVirtualNetworkSubnetConfig `
    -Name $KeyVaultSubnetName `
    -AddressPrefix $KeyVaultSubnetPrefix `
    -PrivateEndpointNetworkPoliciesFlag Disabled

$reservedSubnet = New-AzVirtualNetworkSubnetConfig `
    -Name $ReservedSubnetName `
    -AddressPrefix $ReservedSubnetPrefix

$vnet = New-AzVirtualNetwork `
    -Name $VNetName `
    -ResourceGroupName $ResourceGroupName `
    -Location $Location `
    -AddressPrefix $VNetAddressPrefix `
    -Subnet $appSubnet, $postgresSubnet, $keyVaultSubnet, $reservedSubnet `
    -Tag $Tags

$postgresTemplate = @{
    '$schema' = "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
    contentVersion = "1.0.0.0"
    parameters = @{
        serverName = @{ type = "string" }
        databaseName = @{ type = "string" }
        tenantId = @{ type = "string" }
        entraAdminObjectId = @{ type = "string" }
        entraAdminName = @{ type = "string" }
        entraAdminType = @{ type = "string" }
    }
    resources = @(
        @{
            type = "Microsoft.DBforPostgreSQL/flexibleServers"
            apiVersion = "2024-08-01"
            name = "[parameters('serverName')]"
            location = $Location
            tags = $Tags
            sku = @{
                name = $PostgresSkuName
                tier = $PostgresSkuTier
            }
            properties = @{
                version = $PostgresVersion
                authConfig = @{
                    activeDirectoryAuth = $PostgresActiveDirectoryAuth
                    passwordAuth = $PostgresPasswordAuth
                    tenantId = "[parameters('tenantId')]"
                }
                backup = @{
                    backupRetentionDays = $PostgresBackupRetentionDays
                    geoRedundantBackup = $PostgresGeoRedundantBackup
                }
                highAvailability = @{
                    mode = $PostgresHighAvailabilityMode
                }
                network = @{
                    publicNetworkAccess = $PostgresPublicNetworkAccess
                }
                storage = @{
                    autoGrow = $PostgresStorageAutoGrow
                    storageSizeGB = $PostgresStorageSizeGB
                }
            }
        }
        @{
            type = "Microsoft.DBforPostgreSQL/flexibleServers/administrators"
            apiVersion = "2024-03-01-preview"
            name = "[format('{0}/{1}', parameters('serverName'), parameters('entraAdminObjectId'))]"
            dependsOn = @(
                "[resourceId('Microsoft.DBforPostgreSQL/flexibleServers', parameters('serverName'))]"
            )
            properties = @{
                principalName = "[parameters('entraAdminName')]"
                principalType = "[parameters('entraAdminType')]"
                tenantId = "[parameters('tenantId')]"
            }
        }
        @{
            type = "Microsoft.DBforPostgreSQL/flexibleServers/databases"
            apiVersion = "2024-08-01"
            name = "[format('{0}/{1}', parameters('serverName'), parameters('databaseName'))]"
            dependsOn = @(
                "[resourceId('Microsoft.DBforPostgreSQL/flexibleServers', parameters('serverName'))]"
            )
            properties = @{
                charset = $PostgresDatabaseCharset
                collation = $PostgresDatabaseCollation
            }
        }
    )
}

New-AzResourceGroupDeployment `
    -Name "postgres-$suffix" `
    -ResourceGroupName $ResourceGroupName `
    -TemplateObject $postgresTemplate `
    -serverName $PostgresServerName `
    -databaseName $PostgresDatabaseName `
    -tenantId $context.Tenant.Id `
    -entraAdminObjectId $PostgresEntraAdminObjectId `
    -entraAdminName $PostgresEntraAdminName `
    -entraAdminType $PostgresEntraAdminType | Out-Null

$postgres = Get-AzResource `
    -ResourceGroupName $ResourceGroupName `
    -ResourceType "Microsoft.DBforPostgreSQL/flexibleServers" `
    -Name $PostgresServerName

$vault = New-AzKeyVault `
    -Name $KeyVaultName `
    -ResourceGroupName $ResourceGroupName `
    -Location $Location `
    -Sku $KeyVaultSku `
    -PublicNetworkAccess $KeyVaultPublicNetworkAccess `
    -SoftDeleteRetentionInDays $KeyVaultSoftDeleteRetentionDays `
    -Tag $Tags

$postgresDnsZone = New-AzPrivateDnsZone `
    -ResourceGroupName $ResourceGroupName `
    -Name $PostgresPrivateDnsZoneName `
    -Tag $Tags

New-AzPrivateDnsVirtualNetworkLink `
    -ResourceGroupName $ResourceGroupName `
    -ZoneName $postgresDnsZone.Name `
    -Name $PostgresPrivateDnsLinkName `
    -VirtualNetworkId $vnet.Id `
    -Tag $Tags | Out-Null

$keyVaultDnsZone = New-AzPrivateDnsZone `
    -ResourceGroupName $ResourceGroupName `
    -Name $KeyVaultPrivateDnsZoneName `
    -Tag $Tags

New-AzPrivateDnsVirtualNetworkLink `
    -ResourceGroupName $ResourceGroupName `
    -ZoneName $keyVaultDnsZone.Name `
    -Name $KeyVaultPrivateDnsLinkName `
    -VirtualNetworkId $vnet.Id `
    -Tag $Tags | Out-Null

$postgresPeConnection = New-AzPrivateLinkServiceConnection `
    -Name $PostgresPrivateEndpointConnectionName `
    -PrivateLinkServiceId $postgres.ResourceId `
    -GroupId $PostgresPrivateEndpointGroupId

$postgresPe = New-AzPrivateEndpoint `
    -Name $PostgresPrivateEndpointName `
    -ResourceGroupName $ResourceGroupName `
    -Location $Location `
    -Subnet ($vnet.Subnets | Where-Object Name -eq $PostgresSubnetName) `
    -PrivateLinkServiceConnection $postgresPeConnection `
    -Tag $Tags `
    -Force

$postgresDnsConfig = New-AzPrivateDnsZoneConfig `
    -Name $PostgresPrivateDnsConfigName `
    -PrivateDnsZoneId $postgresDnsZone.ResourceId

New-AzPrivateDnsZoneGroup `
    -ResourceGroupName $ResourceGroupName `
    -PrivateEndpointName $postgresPe.Name `
    -Name $PrivateDnsZoneGroupName `
    -PrivateDnsZoneConfig $postgresDnsConfig `
    -Force | Out-Null

$keyVaultPeConnection = New-AzPrivateLinkServiceConnection `
    -Name $KeyVaultPrivateEndpointConnectionName `
    -PrivateLinkServiceId $vault.ResourceId `
    -GroupId $KeyVaultPrivateEndpointGroupId

$keyVaultPe = New-AzPrivateEndpoint `
    -Name $KeyVaultPrivateEndpointName `
    -ResourceGroupName $ResourceGroupName `
    -Location $Location `
    -Subnet ($vnet.Subnets | Where-Object Name -eq $KeyVaultSubnetName) `
    -PrivateLinkServiceConnection $keyVaultPeConnection `
    -Tag $Tags `
    -Force

$keyVaultDnsConfig = New-AzPrivateDnsZoneConfig `
    -Name $KeyVaultPrivateDnsConfigName `
    -PrivateDnsZoneId $keyVaultDnsZone.ResourceId

New-AzPrivateDnsZoneGroup `
    -ResourceGroupName $ResourceGroupName `
    -PrivateEndpointName $keyVaultPe.Name `
    -Name $PrivateDnsZoneGroupName `
    -PrivateDnsZoneConfig $keyVaultDnsConfig `
    -Force | Out-Null

[pscustomobject]@{
    ResourceGroupName = $ResourceGroupName
    VNetName = $VNetName
    PostgresServerName = $PostgresServerName
    PostgresHost = "$PostgresServerName.postgres.database.azure.com"
    PostgresDatabase = $PostgresDatabaseName
    KeyVaultName = $KeyVaultName
    KeyVaultUri = $vault.VaultUri
}
