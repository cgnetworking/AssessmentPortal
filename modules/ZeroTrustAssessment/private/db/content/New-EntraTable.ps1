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

    function Get-ExportRowsFromFile {
        param([Parameter(Mandatory = $true)][string]$Path)

        $content = Get-Content -Path $Path -Raw
        if (-not $content) { return }

        $json = $content | ConvertFrom-Json
        if ($json.PSObject.Properties.Name -contains 'value') {
            foreach ($item in @($json.value)) { $item }
        }
        elseif ($json -is [array]) {
            foreach ($item in $json) { $item }
        }
        else {
            $json
        }
    }

    function New-InsertValueRow {
        param(
            [Parameter(Mandatory = $true)]
            $Row,

            [Parameter(Mandatory = $true)]
            $ColumnTypes
        )

        $insertValues = @((ConvertTo-SqlLiteral -Value $Row) + '::jsonb')

        foreach ($columnName in $ColumnTypes.Keys) {
            $property = $Row.PSObject.Properties[$columnName]
            $value = if ($property) { $property.Value } else { $null }
            if ($ColumnTypes[$columnName] -eq 'jsonb') {
                $insertValues += ((ConvertTo-SqlLiteral -Value $value) + '::jsonb')
            }
            else {
                $insertValues += ConvertTo-ScalarSqlLiteral -Value $value
            }
        }

        "($($insertValues -join ', '))"
    }

    function Invoke-InsertBatch {
        param(
            [Parameter(Mandatory = $true)]
            $Database,

            [Parameter(Mandatory = $true)]
            [string]
            $InsertPrefix,

            [Parameter(Mandatory = $true)]
            [System.Collections.Generic.List[string]]
            $ValueRows
        )

        if ($ValueRows.Count -eq 0) { return }

        $sql = $InsertPrefix + ($ValueRows -join ', ') + ';'
        Invoke-DatabaseQuery -Database $Database -Sql $sql -NonQuery
    }

    Write-PSFMessage "Importing PostgreSQL table $TableName from $FilePath" -Tag Import

    $schema = if ($Database.Schema) { $Database.Schema } else { 'main' }
    $schemaIdentifier = ConvertTo-SqlIdentifier -Name $schema
    $tableIdentifier = ConvertTo-SqlIdentifier -Name $TableName

    $files = @(Get-ChildItem -Path $FilePath -File -ErrorAction SilentlyContinue)
    $columnTypes = [ordered]@{}
    $hasRows = $false
    foreach ($file in $files) {
        foreach ($row in (Get-ExportRowsFromFile -Path $file.FullName)) {
            $hasRows = $true
            foreach ($property in $row.PSObject.Properties) {
                if (-not $columnTypes.Contains($property.Name) -and $null -ne $property.Value) {
                    $columnTypes[$property.Name] = Get-PostgresColumnType -Value $property.Value
                }
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

    if (-not $hasRows) {
        return
    }

    $insertColumns = @('"__zt_raw"')
    foreach ($columnName in $columnTypes.Keys) {
        $insertColumns += ConvertTo-SqlIdentifier -Name $columnName
    }
    $insertPrefix = "INSERT INTO $schemaIdentifier.$tableIdentifier ($($insertColumns -join ', ')) VALUES "
    $batchSize = 500
    $maxSqlLength = 1MB
    $valueRows = [System.Collections.Generic.List[string]]::new()
    $currentSqlLength = $insertPrefix.Length

    foreach ($file in $files) {
        foreach ($row in (Get-ExportRowsFromFile -Path $file.FullName)) {
            $valueRow = New-InsertValueRow -Row $row -ColumnTypes $columnTypes
            $valueRowLength = $valueRow.Length + 2

            if ($valueRows.Count -gt 0 -and ($valueRows.Count -ge $batchSize -or ($currentSqlLength + $valueRowLength) -gt $maxSqlLength)) {
                Invoke-InsertBatch -Database $Database -InsertPrefix $insertPrefix -ValueRows $valueRows
                $valueRows.Clear()
                $currentSqlLength = $insertPrefix.Length
            }

            $valueRows.Add($valueRow)
            $currentSqlLength += $valueRowLength
        }
    }

    Invoke-InsertBatch -Database $Database -InsertPrefix $insertPrefix -ValueRows $valueRows
}
