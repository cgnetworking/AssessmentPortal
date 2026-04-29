#!/usr/bin/env bash

build_frontend() {
    if [[ "${BUILD_FRONTEND}" -eq 0 ]]; then
        log "Skipping frontend build."
        return
    fi

    log "Installing pinned frontend packages and building React assets."
    pushd "${INSTALL_DIR}/frontend" >/dev/null
    if [[ -f package-lock.json ]]; then
        runuser -u "${APP_USER}" -- npm ci
    else
        runuser -u "${APP_USER}" -- npm install
    fi
    runuser -u "${APP_USER}" -- npm run build
    popd >/dev/null
}
