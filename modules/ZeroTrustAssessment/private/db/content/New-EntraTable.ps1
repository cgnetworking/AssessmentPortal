<#
.SYNOPSIS
    Creates a PostgreSQL table from exported Microsoft Graph JSON.
#>

function New-EntraTable {
    [CmdletBinding()]
    param (
        [Parameter(Mandatory = $true)]
        $Database,

        [Parameter(Mandatory = $true)]
        [string]
        $TableName,

        [Parameter(Mandatory = $true)]
        [string]
        $FilePath
    )

    function ConvertTo-SqlIdentifier {
        param([Parameter(Mandatory = $true)][string]$Name)
        '"' + ($Name -replace '"', '""') + '"'
    }

    function ConvertTo-SqlLiteral {
        param($Value)
        if ($null -eq $Value) { return 'NULL' }
        "'" + (($Value | ConvertTo-Json -Depth 100 -Compress) -replace "'", "''") + "'"
    }

    function ConvertTo-ScalarSqlLiteral {
        param($Value)
        if ($null -eq $Value) { return 'NULL' }
        if ($Value -is [bool]) {
            if ($Value) { return 'true' }
            return 'false'
        }
        "'" + ([string]$Value -replace "'", "''") + "'"
    }

    function Get-PostgresColumnType {
        param($Value)
        if ($Value -is [bool]) { return 'boolean' }
        if ($Value -is [byte] -or $Value -is [int16] -or $Value -is [int] -or $Value -is [long] -or $Value -is [decimal] -or $Value -is [double] -or $Value -is [single]) { return 'numeric' }
        if ($Value -is [array] -or $Value -is [System.Management.Automation.PSCustomObject] -or $Value -is [hashtable]) { return 'jsonb' }
        return 'text'
    }

    Write-PSFMessage "Importing PostgreSQL table $TableName from $FilePath" -Tag Import

    $rows = [System.Collections.Generic.List[object]]::new()
    foreach ($file in Get-ChildItem -Path $FilePath -File -ErrorAction SilentlyContinue) {
        $content = Get-Content -Path $file.FullName -Raw
        if (-not $content) { continue }

        $json = $content | ConvertFrom-Json
        if ($json.PSObject.Properties.Name -contains 'value') {
            foreach ($item in @($json.value)) { $rows.Add($item) }
        }
        elseif ($json -is [array]) {
            foreach ($item in $json) { $rows.Add($item) }
        }
        else {
            $rows.Add($json)
        }
    }

    $schema = if ($Database.Schema) { $Database.Schema } else { 'main' }
    $schemaIdentifier = ConvertTo-SqlIdentifier -Name $schema
    $tableIdentifier = ConvertTo-SqlIdentifier -Name $TableName

    $columnTypes = [ordered]@{}
    foreach ($row in $rows) {
        foreach ($property in $row.PSObject.Properties) {
            if (-not $columnTypes.Contains($property.Name) -and $null -ne $property.Value) {
                $columnTypes[$property.Name] = Get-PostgresColumnType -Value $property.Value
            }
        }
    }

    $columns = @('"__zt_raw" jsonb')
    foreach ($columnName in $columnTypes.Keys) {
        $columns += ('{0} {1}' -f (ConvertTo-SqlIdentifier -Name $columnName), $columnTypes[$columnName])
    }

    Invoke-DatabaseQuery -Database $Database -Sql "CREATE SCHEMA IF NOT EXISTS $schemaIdentifier;" -NonQuery
    Invoke-DatabaseQuery -Database $Database -Sql "DROP TABLE IF EXISTS $schemaIdentifier.$tableIdentifier CASCADE;" -NonQuery
    Invoke-DatabaseQuery -Database $Database -Sql "CREATE TABLE $schemaIdentifier.$tableIdentifier ($($columns -join ', '));" -NonQuery

    if ($rows.Count -eq 0) {
        return
    }

    foreach ($row in $rows) {
        $insertColumns = @('"__zt_raw"')
        $insertValues = @((ConvertTo-SqlLiteral -Value $row) + '::jsonb')

        foreach ($columnName in $columnTypes.Keys) {
            $value = $row.PSObject.Properties[$columnName].Value
            $insertColumns += ConvertTo-SqlIdentifier -Name $columnName
            if ($columnTypes[$columnName] -eq 'jsonb') {
                $insertValues += ((ConvertTo-SqlLiteral -Value $value) + '::jsonb')
            }
            else {
                $insertValues += ConvertTo-ScalarSqlLiteral -Value $value
            }
        }

        $sql = "INSERT INTO $schemaIdentifier.$tableIdentifier ($($insertColumns -join ', ')) VALUES ($($insertValues -join ', '));"
        Invoke-DatabaseQuery -Database $Database -Sql $sql -NonQuery
    }
}
