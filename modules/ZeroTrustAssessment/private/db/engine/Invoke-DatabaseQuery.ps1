function Invoke-DatabaseQuery {
	<#
	.SYNOPSIS
		Executes SQL against PostgreSQL.
	#>
	[CmdletBinding()]
	param (
		$Database,

		[Parameter(Mandatory = $true)]
		[Alias('Query')]
		[string]
		$Sql,

		[switch]
		$NonQuery,

		[switch]
		$Ordered,

		[switch]
		$AsCustomObject
	)

	function Invoke-ZtPsql {
		[CmdletBinding()]
		param (
			[Parameter(Mandatory = $true)]
			$Db,

			[Parameter(Mandatory = $true)]
			[string]
			$CommandText
		)

		$args = @('-X', '-q', '-t', '-A', '-v', 'ON_ERROR_STOP=1')
		if ($Db.ConnectionString) {
			$args += $Db.ConnectionString
		}
		$args += @('-c', $CommandText)

		$output = & psql @args 2>&1
		if ($LASTEXITCODE -ne 0) {
			$message = ($output | Out-String).Trim()
			throw "PostgreSQL query failed: $message`nSQL: $CommandText"
		}
		($output | Out-String).Trim()
	}

	function ConvertTo-PostgreSqlQuery {
		[CmdletBinding()]
		param (
			[Parameter(Mandatory = $true)]
			[string]
			$Query
		)

		$translated = $Query
		$translated = $translated -replace '\bCREATE\s+OR\s+REPLACE\s+VIEW\b', 'CREATE OR REPLACE VIEW'
		$translated = $translated -replace '\bmain\.', ('"{0}".' -f (($dbToUse.Schema) -replace '"', '""'))

		# Translate the common struct access pattern used by exported Graph objects.
		$translated = [regex]::Replace($translated, '(\b[a-zA-Z_][a-zA-Z0-9_]*\."?[a-zA-Z_@][a-zA-Z0-9_@.-]*"?)\.("[^"]+"|[a-zA-Z_@][a-zA-Z0-9_@.-]*)', {
			param($m)
			$left = $m.Groups[1].Value
			$field = $m.Groups[2].Value.Trim('"')
			"$left ->> '$($field -replace "'", "''")'"
		})

		$translated
	}

	$dbToUse = $Database
	if (-not $dbToUse) { $dbToUse = $script:_DatabaseConnection }
	if (-not $dbToUse) {
		Stop-PSFFunction -Message "No PostgreSQL database handle provided, cannot execute SQL statement. Use Connect-Database first." -Cmdlet $PSCmdlet -EnableException $true -Category ConnectionError -Tag DB
	}

	$sqlToRun = ConvertTo-PostgreSqlQuery -Query $Sql
	Write-PSFMessage "Running PostgreSQL query: $sqlToRun" -Level Debug -Tag DB

	if ($NonQuery) {
		$null = Invoke-ZtPsql -Db $dbToUse -CommandText $sqlToRun
		return
	}

	$query = $sqlToRun.Trim().TrimEnd(';')
	$jsonSql = "SELECT COALESCE(jsonb_agg(to_jsonb(q)), '[]'::jsonb)::text FROM ($query) q;"
	$json = Invoke-ZtPsql -Db $dbToUse -CommandText $jsonSql
	if (-not $json) { return }

	$rows = $json | ConvertFrom-Json
	foreach ($row in @($rows)) {
		if ($Ordered) { $rowObject = [ordered]@{} }
		else { $rowObject = @{} }

		foreach ($property in $row.PSObject.Properties) {
			$rowObject[$property.Name] = $property.Value
		}

		if ($AsCustomObject) { [PSCustomObject]$rowObject }
		else { $rowObject }
	}
}
