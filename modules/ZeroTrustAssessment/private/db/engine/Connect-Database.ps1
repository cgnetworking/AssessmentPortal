function Connect-Database {
	<#
	.SYNOPSIS
		Creates a PostgreSQL database handle.

	.DESCRIPTION
		Creates a PostgreSQL database handle used by Invoke-DatabaseQuery.
		The handle intentionally contains connection metadata only. Query execution is
		performed through psql so this fork does not load native database
		assemblies.

		Set ZT_POSTGRES_CONNECTION_STRING, DATABASE_URL, or standard PG* environment
		variables before calling this command. For Azure Database for PostgreSQL with
		managed identity, the worker should provide the Entra access token through
		PGPASSWORD or the password field in ZT_POSTGRES_CONNECTION_STRING.
	#>
	[CmdletBinding()]
	param (
		[string]
		$Path,

		[string]
		$ConnectionString = $env:ZT_POSTGRES_CONNECTION_STRING,

		[string]
		$Schema = $(if ($env:ZT_POSTGRES_SCHEMA) { $env:ZT_POSTGRES_SCHEMA } else { 'main' }),

		[switch]
		$PassThru,

		[switch]
		$Transient
	)

	if (-not $ConnectionString -and $env:DATABASE_URL) {
		$ConnectionString = $env:DATABASE_URL
	}

	Write-PSFMessage -Level System -Message 'Establishing a PostgreSQL assessment database handle for schema {0}' -StringValues $Schema -Tag DB

	$database = [PSCustomObject]@{
		PSTypeName        = 'ZeroTrustAssessment.PostgreSqlConnection'
		Provider          = 'PostgreSQL'
		ConnectionString  = $ConnectionString
		Schema            = $Schema
		LegacyPath        = $Path
	}

	Invoke-DatabaseQuery -Database $database -Sql ('CREATE SCHEMA IF NOT EXISTS "{0}";' -f ($Schema -replace '"', '""')) -NonQuery

	if ($PassThru -or $Transient) { $database }
	if (-not $Transient) {
		$script:_DatabaseConnection = $database
	}
}
