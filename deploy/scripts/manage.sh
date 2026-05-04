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

while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%$'\r'}"
    [[ -z "${line//[[:space:]]/}" ]] && continue
    [[ "${line}" =~ ^[[:space:]]*# ]] && continue

    line="${line#"${line%%[![:space:]]*}"}"
    [[ "${line}" == export[[:space:]]* ]] && line="${line#export}"
    line="${line#"${line%%[![:space:]]*}"}"

    if [[ "${line}" != *=* ]]; then
        echo "Invalid environment line in ${ENV_FILE}: ${line}" >&2
        exit 1
    fi

    key="${line%%=*}"
    value="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"

    if [[ ! "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo "Invalid environment key in ${ENV_FILE}: ${key}" >&2
        exit 1
    fi

    if [[ "${value}" == \"*\" && "${value}" == *\" && "${#value}" -ge 2 ]]; then
        value="${value:1:${#value}-2}"
    elif [[ "${value}" == \'*\' && "${value}" == *\' && "${#value}" -ge 2 ]]; then
        value="${value:1:${#value}-2}"
    fi

    export "${key}=${value}"
done < "${ENV_FILE}"

cd "${INSTALL_DIR}/backend"

if [[ "$(id -u)" -eq 0 ]] && id "${APP_USER}" >/dev/null 2>&1; then
    exec runuser -u "${APP_USER}" -- env HOME="${DATA_DIR}" "${PYTHON_BIN}" manage.py "$@"
fi

export HOME="${HOME:-${DATA_DIR}}"
exec "${PYTHON_BIN}" manage.py "$@"
