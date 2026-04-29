$script:ZtPostgresAccessToken = $null
$script:ZtPostgresAccessTokenExpiresAtUtc = [DateTime]::MinValue

function ConvertTo-ZtManagedIdentityExpiresOnUtc {
	[CmdletBinding()]
	param (
		$ExpiresOn
	)

	if (-not $ExpiresOn) {
		return [DateTime]::UtcNow.AddMinutes(55)
	}

	$expiresOnText = [string]$ExpiresOn
	$unixSeconds = 0L
	if ([long]::TryParse($expiresOnText, [ref]$unixSeconds)) {
		return [DateTimeOffset]::FromUnixTimeSeconds($unixSeconds).UtcDateTime
	}

	$parsed = [DateTimeOffset]::MinValue
	if ([DateTimeOffset]::TryParse($expiresOnText, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AssumeUniversal, [ref]$parsed)) {
		return $parsed.UtcDateTime
	}

	return [DateTime]::UtcNow.AddMinutes(55)
}

function Get-ZtPostgresManagedIdentityTokenResponse {
	[CmdletBinding()]
	param (
		[Parameter(Mandatory = $true)]
		[string]
		$Resource
	)

	$encodedResource = [uri]::EscapeDataString($Resource)
	$clientId = if ($env:AZURE_CLIENT_ID) { $env:AZURE_CLIENT_ID } else { $env:AZURE_MANAGED_IDENTITY_CLIENT_ID }

	if ($env:IDENTITY_ENDPOINT -and $env:IDENTITY_HEADER) {
		$uri = "$($env:IDENTITY_ENDPOINT)?api-version=2019-08-01&resource=$encodedResource"
		if ($clientId) {
			$uri = "$uri&client_id=$([uri]::EscapeDataString($clientId))"
		}

		return Invoke-RestMethod -Method GET -Uri $uri -Headers @{
			'X-IDENTITY-HEADER' = $env:IDENTITY_HEADER
		} -TimeoutSec 10
	}

	$uri = "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=$encodedResource"
	if ($clientId) {
		$uri = "$uri&client_id=$([uri]::EscapeDataString($clientId))"
	}

	Invoke-RestMethod -Method GET -Uri $uri -Headers @{ Metadata = 'true' } -TimeoutSec 10
}

function Get-ZtPostgresAccessToken {
	[CmdletBinding()]
	param()

	$refreshAtUtc = [DateTime]::UtcNow.AddMinutes(5)
	if ($script:ZtPostgresAccessToken -and $script:ZtPostgresAccessTokenExpiresAtUtc -gt $refreshAtUtc) {
		return $script:ZtPostgresAccessToken
	}

	$resource = if ($env:ZT_POSTGRES_TOKEN_RESOURCE) { $env:ZT_POSTGRES_TOKEN_RESOURCE } else { 'https://ossrdbms-aad.database.windows.net' }
	$response = Get-ZtPostgresManagedIdentityTokenResponse -Resource $resource
	if (-not $response.access_token) {
		throw 'Managed identity token response did not include an access token for PostgreSQL.'
	}

	$script:ZtPostgresAccessToken = $response.access_token
	$script:ZtPostgresAccessTokenExpiresAtUtc = ConvertTo-ZtManagedIdentityExpiresOnUtc -ExpiresOn $response.expires_on
	$script:ZtPostgresAccessToken
}

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

		$previousPassword = [Environment]::GetEnvironmentVariable('PGPASSWORD', 'Process')
		try {
			$env:PGPASSWORD = Get-ZtPostgresAccessToken
			$output = & psql @args 2>&1
			$exitCode = $LASTEXITCODE
		}
		finally {
			if ($null -eq $previousPassword) {
				Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
			}
			else {
				$env:PGPASSWORD = $previousPassword
			}
		}

		if ($exitCode -ne 0) {
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
