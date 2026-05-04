function Assert-RequiredModules {
    [CmdletBinding()]
    param (
        [Parameter(Mandatory, ValueFromPipeline)]
        [AllowNull()]
        [Microsoft.PowerShell.Commands.ModuleSpecification[]] $ModuleSpecification,

        [Parameter()]
        [switch] $PassThru
    )

    begin {
        function Get-ZtModuleSpecificationName {
            param (
                [Parameter(ValueFromPipeline = $true)]
                [AllowNull()]
                $ModuleSpecification
            )

            process {
                if ($null -eq $ModuleSpecification) {
                    return
                }

                $properties = $ModuleSpecification.PSObject.Properties
                if ($properties['Name']) {
                    return $ModuleSpecification.Name
                }
                if ($properties['ModuleName']) {
                    return $ModuleSpecification.ModuleName
                }
            }
        }
    }

    process {
        foreach ($moduleSpec in $ModuleSpecification) {
            $moduleSpecName = $moduleSpec | Get-ZtModuleSpecificationName
            $getModuleParams = @{
                ListAvailable = $true
                FullyQualifiedName = $moduleSpec
            }

            $availableModule = (Get-Module @getModuleParams).Where({$_.Guid -eq $moduleSpec.Guid}, 1) # take only the first match

            if (-not $availableModule) {
                throw ("Required module '{0}' cannot be found in the current `$Env:PSModulePath." -f $moduleSpec)
            }
            else {
                Write-Verbose -Message ("Module '{0}' is available with version v{1}." -f $moduleSpecName, $availableModule.Version)
                if ($PassThru.IsPresent) {
                    $availableModule
                }
            }
        }
    }
}
