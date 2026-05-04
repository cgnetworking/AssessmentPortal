#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="assessmentportal"
APP_SERVICES=(assessmentportal-gunicorn assessmentportal-worker)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SYSTEMD_DIR="${REPO_ROOT}/deploy/systemd"

log() {
    printf '[%s] %s\n' "${APP_NAME}" "$*"
}

fail() {
    printf '[%s] ERROR: %s\n' "${APP_NAME}" "$*" >&2
    exit 1
}

[[ "${EUID}" -eq 0 ]] || fail "Run as root with sudo."

install_systemd_units() {
    local needs_reload=0

    for service in "${APP_SERVICES[@]}"; do
        local unit_file="${service}.service"
        local source_unit="${SYSTEMD_DIR}/${unit_file}"
        local target_unit="/etc/systemd/system/${unit_file}"

        [[ -f "${source_unit}" ]] || fail "Systemd unit template not found: ${source_unit}"

        if [[ ! -f "${target_unit}" ]] || ! cmp -s "${source_unit}" "${target_unit}"; then
            log "Installing systemd unit ${unit_file}."
            install -m 0644 "${source_unit}" "${target_unit}"
            needs_reload=1
        fi
    done

    if [[ "${needs_reload}" -eq 1 ]]; then
        log "Reloading systemd unit definitions."
        systemctl daemon-reload
    fi
}

install_systemd_units

log "Enabling application services."
systemctl enable "${APP_SERVICES[@]}"

log "Restarting application services."
systemctl restart "${APP_SERVICES[@]}"

log "Validating NGINX configuration."
nginx -t

log "Reloading NGINX."
systemctl reload nginx

log "Services restarted."
