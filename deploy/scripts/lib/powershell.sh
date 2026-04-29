#!/usr/bin/env bash

install_powershell_dependencies() {
    if ! command -v pwsh >/dev/null 2>&1; then
        fail "PowerShell is required to install ZeroTrustAssessment dependencies. Install it or rerun without --skip-powershell-install."
    fi

    log "Installing pinned ZeroTrustAssessment PowerShell dependencies for the application user."
    runuser -u "${APP_USER}" -- env HOME="${DATA_DIR}" pwsh -NoLogo -NoProfile -Command "Import-Module '${INSTALL_DIR}/modules/ZeroTrustAssessment/ZeroTrustAssessment.psd1' -Force"
}
