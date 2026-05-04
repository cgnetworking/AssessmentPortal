#!/usr/bin/env bash
set -Eeuo pipefail

APP_USER="${APP_USER:-assessmentportal}"
INSTALL_DIR="${INSTALL_DIR:-/opt/assessmentportal}"
DATA_DIR="${DATA_DIR:-/var/lib/assessmentportal}"
ENV_FILE="${ENV_FILE:-/etc/assessmentportal/assessmentportal.env}"
PYTHON_BIN="${PYTHON_BIN:-${INSTALL_DIR}/.venv/bin/python}"

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 <django-management-command> [args...]" >&2
    exit 2
fi

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Environment file not found: ${ENV_FILE}" >&2
    exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Python virtual environment not found: ${PYTHON_BIN}" >&2
    exit 1
fi

set -a
# shellcheck source=/dev/null
. "${ENV_FILE}"
set +a

cd "${INSTALL_DIR}/backend"

if [[ "$(id -u)" -eq 0 ]] && id "${APP_USER}" >/dev/null 2>&1; then
    exec runuser -u "${APP_USER}" -- env HOME="${DATA_DIR}" "${PYTHON_BIN}" manage.py "$@"
fi

export HOME="${HOME:-${DATA_DIR}}"
exec "${PYTHON_BIN}" manage.py "$@"
