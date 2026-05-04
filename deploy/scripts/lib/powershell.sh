#!/usr/bin/env bash

install_powershell_dependencies() {
    if ! command -v pwsh >/dev/null 2>&1; then
        fail "PowerShell is required to install ZeroTrustAssessment dependencies. Install it or rerun without --skip-powershell-install."
    fi

    local module_root="${INSTALL_DIR}/modules/ZeroTrustAssessment"

    log "Installing pinned ZeroTrustAssessment PowerShell dependencies for the application user."
    runuser -u "${APP_USER}" -- env HOME="${DATA_DIR}" pwsh -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "\$ErrorActionPreference = 'Stop'
\$moduleRoot = '${module_root}'
\$manifest = Join-Path \$moduleRoot 'ZeroTrustAssessment.psd1'
\$requiredModulesPath = Join-Path \$env:HOME '.cache/ZeroTrustAssessment/Modules'
& (Join-Path \$moduleRoot 'Initialize-Dependencies.ps1') -ModuleManifestPath \$manifest -RequiredModulesPath \$requiredModulesPath
\$separator = [System.IO.Path]::PathSeparator
\$modulePath = @(\$env:PSModulePath -split \$separator | Where-Object { \$_ })
\$normalizedModulePath = \$modulePath | ForEach-Object { \$_.TrimEnd([System.IO.Path]::DirectorySeparatorChar) }
if (\$requiredModulesPath.TrimEnd([System.IO.Path]::DirectorySeparatorChar) -notin \$normalizedModulePath) {
    \$env:PSModulePath = (@(\$requiredModulesPath) + \$modulePath) -join \$separator
}
Import-Module \$manifest -Force"
}
