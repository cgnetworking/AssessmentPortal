function Disconnect-Database {
	<#
	.SYNOPSIS
		Clears the PostgreSQL database handle.
	#>
	[CmdletBinding()]
	param (
		$Database
	)

	if ($Database -and $script:_DatabaseConnection -eq $Database) {
		$script:_DatabaseConnection = $null
		return
	}

	if (-not $Database -and $script:_DatabaseConnection) {
		$script:_DatabaseConnection = $null
	}
}
