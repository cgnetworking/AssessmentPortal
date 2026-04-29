#!/usr/bin/env bash

usage() {
    cat <<USAGE
Usage: sudo deploy/scripts/setup_ubuntu.sh [options]

Options:
  --domain <host>                Public portal hostname. Default: ${DOMAIN}
  --install-dir <path>           Install path. Default: ${INSTALL_DIR}
  --data-dir <path>              Runtime data path. Default: ${DATA_DIR}
  --pip-version <version>        Pinned pip version. Default: ${PIP_VERSION}
  --wheel-version <version>      Pinned wheel version. Default: ${WHEEL_VERSION}
  --powershell-version <version> Pinned apt package version. Default: ${POWERSHELL_VERSION}
  --skip-node-install            Do not install Ubuntu nodejs/npm packages.
  --skip-powershell-install      Do not install PowerShell from the Microsoft apt repository.
  --skip-frontend-build          Do not run npm install/build.
  --skip-migrations             Do not run Django migrate/collectstatic.
  --skip-service-start           Install systemd units but do not enable/start them.
  --skip-nginx                  Do not install the NGINX site config.
  -h, --help                    Show this help.

Run this script from the repository checkout on Ubuntu 24.04 or newer.
Edit ${ENV_FILE} before starting services if the script reports placeholders.
USAGE
}

log() {
    printf '[%s] %s\n' "${APP_NAME}" "$*"
}

fail() {
    printf '[%s] ERROR: %s\n' "${APP_NAME}" "$*" >&2
    exit 1
}

assert_supported_host() {
    [[ "${EUID}" -eq 0 ]] || fail "Run as root with sudo."
    [[ -f /etc/os-release ]] || fail "Cannot determine operating system."

    # shellcheck source=/dev/null
    . /etc/os-release
    [[ "${ID:-}" == "ubuntu" ]] || fail "This setup script supports Ubuntu only."
    if [[ "${VERSION_ID%%.*}" -lt 24 ]]; then
        fail "Ubuntu 24.04 or newer is required. Found ${VERSION_ID}."
    fi
}

assert_repository_layout() {
    [[ -f "${REPO_ROOT}/requirements.txt" ]] || fail "requirements.txt not found in ${REPO_ROOT}."
    [[ -f "${REPO_ROOT}/backend/manage.py" ]] || fail "backend/manage.py not found in ${REPO_ROOT}."
    [[ -f "${REPO_ROOT}/frontend/package.json" ]] || fail "frontend/package.json not found in ${REPO_ROOT}."
    [[ -f "${REPO_ROOT}/deploy/nginx/assessmentportal.conf" ]] || fail "NGINX template not found."
}

assert_python_runtime() {
    command -v python3.12 >/dev/null 2>&1 || fail "python3.12 is required for the deployment venv."

    local python_version
    python_version="$(python3.12 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"
    [[ "${python_version}" == "3.12" ]] || fail "Expected python3.12 to report Python 3.12; got ${python_version}."
}

env_has_placeholders() {
    grep -Eq 'replace-|assessment\.example\.com' "${ENV_FILE}"
}

load_env_file() {
    local line key value
    while IFS= read -r line || [[ -n "${line}" ]]; do
        [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]] && continue
        key="${line%%=*}"
        value="${line#*=}"
        [[ -n "${key}" && "${key}" != "${line}" ]] || continue
        export "${key}=${value}"
    done < "${ENV_FILE}"
}
