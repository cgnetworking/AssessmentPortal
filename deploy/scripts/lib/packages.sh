#!/usr/bin/env bash

install_base_packages() {
    log "Installing base OS packages."
    apt-get update
    apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        nginx \
        openssl \
        postgresql-client \
        python3-pip \
        python3.12 \
        python3.12-venv \
        rsync \
        software-properties-common \
        wget
}

install_node_packages() {
    if [[ "${INSTALL_NODE}" -eq 0 ]]; then
        log "Skipping nodejs/npm installation."
        return
    fi

    log "Installing nodejs/npm from Ubuntu repositories."
    apt-get install -y nodejs npm

    local node_major
    node_major="$(node -p "Number(process.versions.node.split('.')[0])")"
    if [[ "${node_major}" -lt 18 ]]; then
        fail "Node.js 18 or newer is required. Found $(node --version). Install a newer Node.js package and rerun with --skip-node-install."
    fi
}

install_powershell_package() {
    if [[ "${INSTALL_POWERSHELL}" -eq 0 ]]; then
        log "Skipping PowerShell installation."
        return
    fi

    if command -v pwsh >/dev/null 2>&1; then
        log "PowerShell already installed: $(pwsh -NoLogo -NoProfile -Command '$PSVersionTable.PSVersion.ToString()')"
        return
    fi

    log "Installing PowerShell ${POWERSHELL_VERSION} from the Microsoft apt repository."
    local packages_deb="/tmp/packages-microsoft-prod.deb"
    wget -q "https://packages.microsoft.com/config/ubuntu/${VERSION_ID}/packages-microsoft-prod.deb" -O "${packages_deb}"
    dpkg -i "${packages_deb}"
    rm -f "${packages_deb}"
    apt-get update
    apt-get install -y "powershell=${POWERSHELL_VERSION}"
}
