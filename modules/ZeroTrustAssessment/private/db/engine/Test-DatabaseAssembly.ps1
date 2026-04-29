function Test-DatabaseAssembly {
	<#
	.SYNOPSIS
		Validates that the PostgreSQL command-line client is available.

	.DESCRIPTION
		This fork uses PostgreSQL only. It does not load bundled native
		database binaries, or Windows runtime dependencies. Query execution is
		performed through psql using managed-identity-ready environment variables.
	#>
	[CmdletBinding()]
	param ()

	if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
		Write-Host
		Write-Host "PostgreSQL client 'psql' is required on Ubuntu 24.04+." -ForegroundColor Red
		Write-Host "Install postgresql-client and configure the managed-identity worker to provide PG* environment variables." -ForegroundColor Yellow
		Write-Host
		return $false
	}

	try {
		$database = Connect-Database -Transient
		$result = Invoke-DatabaseQuery -Database $database -Sql 'SELECT 1 AS ok;' -AsCustomObject
		return ($result.ok -eq 1 -or $result.ok -eq '1')
	}
	catch {
		Write-PSFMessage 'PostgreSQL connectivity validation failed' -ErrorRecord $_ -Tag DB -Level Debug
		throw
	}
}
