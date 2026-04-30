#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="assessmentportal"
APP_SERVICES=(assessmentportal-gunicorn assessmentportal-worker)

log() {
    printf '[%s] %s\n' "${APP_NAME}" "$*"
}

fail() {
    printf '[%s] ERROR: %s\n' "${APP_NAME}" "$*" >&2
    exit 1
}

[[ "${EUID}" -eq 0 ]] || fail "Run as root with sudo."

log "Restarting application services."
systemctl restart "${APP_SERVICES[@]}"

log "Validating NGINX configuration."
nginx -t

log "Reloading NGINX."
systemctl reload nginx

log "Services restarted."
