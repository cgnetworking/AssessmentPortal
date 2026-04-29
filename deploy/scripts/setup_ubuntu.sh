#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="assessmentportal"
APP_USER="assessmentportal"
APP_GROUP="assessmentportal"
WEB_GROUP="www-data"
INSTALL_DIR="/opt/assessmentportal"
DATA_DIR="/var/lib/assessmentportal"
ENV_DIR="/etc/assessmentportal"
ENV_FILE="${ENV_DIR}/assessmentportal.env"
DOMAIN="assessment.example.com"
PIP_VERSION="25.3"
WHEEL_VERSION="0.45.1"
POWERSHELL_VERSION="7.5.6-1.deb"
INSTALL_NODE=1
INSTALL_POWERSHELL=1
BUILD_FRONTEND=1
RUN_MIGRATIONS=1
START_SERVICES=1
CONFIGURE_NGINX=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=deploy/scripts/lib/packages.sh
. "${SCRIPT_DIR}/lib/packages.sh"
# shellcheck source=deploy/scripts/lib/filesystem.sh
. "${SCRIPT_DIR}/lib/filesystem.sh"
# shellcheck source=deploy/scripts/lib/python.sh
. "${SCRIPT_DIR}/lib/python.sh"
# shellcheck source=deploy/scripts/lib/frontend.sh
. "${SCRIPT_DIR}/lib/frontend.sh"
# shellcheck source=deploy/scripts/lib/powershell.sh
. "${SCRIPT_DIR}/lib/powershell.sh"
# shellcheck source=deploy/scripts/lib/config.sh
. "${SCRIPT_DIR}/lib/config.sh"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)
            DOMAIN="${2:?Missing value for --domain}"
            shift 2
            ;;
        --install-dir)
            INSTALL_DIR="${2:?Missing value for --install-dir}"
            shift 2
            ;;
        --data-dir)
            DATA_DIR="${2:?Missing value for --data-dir}"
            shift 2
            ;;
        --pip-version)
            PIP_VERSION="${2:?Missing value for --pip-version}"
            shift 2
            ;;
        --wheel-version)
            WHEEL_VERSION="${2:?Missing value for --wheel-version}"
            shift 2
            ;;
        --powershell-version)
            POWERSHELL_VERSION="${2:?Missing value for --powershell-version}"
            shift 2
            ;;
        --skip-node-install)
            INSTALL_NODE=0
            shift
            ;;
        --skip-powershell-install)
            INSTALL_POWERSHELL=0
            shift
            ;;
        --skip-frontend-build)
            BUILD_FRONTEND=0
            shift
            ;;
        --skip-migrations)
            RUN_MIGRATIONS=0
            shift
            ;;
        --skip-service-start)
            START_SERVICES=0
            shift
            ;;
        --skip-nginx)
            CONFIGURE_NGINX=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "Unknown option: $1"
            ;;
    esac
done

main() {
    assert_supported_host
    assert_repository_layout

    log "Starting setup for ${DOMAIN} on Ubuntu ${VERSION_ID}."
    install_base_packages
    assert_python_runtime
    install_node_packages
    install_powershell_package
    ensure_users_and_directories
    copy_application_files
    validate_no_duckdb_files
    create_python_environment
    build_frontend
    write_environment_file
    install_powershell_dependencies
    run_django_setup
    install_systemd_units
    configure_nginx
    start_services

    log "Setup complete."
    if env_has_placeholders; then
        log "Next step: edit ${ENV_FILE}, then run:"
        log "  ${INSTALL_DIR}/deploy/scripts/setup_ubuntu.sh --domain ${DOMAIN} --skip-node-install --skip-powershell-install --skip-frontend-build"
    fi
}

main "$@"
