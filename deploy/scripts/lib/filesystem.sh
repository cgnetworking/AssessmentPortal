#!/usr/bin/env bash

ensure_users_and_directories() {
    log "Creating application user, groups, and directories."

    if ! getent group "${APP_GROUP}" >/dev/null; then
        groupadd --system "${APP_GROUP}"
    fi

    if ! id "${APP_USER}" >/dev/null 2>&1; then
        useradd --system --gid "${APP_GROUP}" --home-dir "${DATA_DIR}" --create-home --shell /usr/sbin/nologin "${APP_USER}"
    fi

    mkdir -p "${INSTALL_DIR}" "${ENV_DIR}" "${DATA_DIR}/assessment-work" "${DATA_DIR}/.cache"
    chown -R "${APP_USER}:${APP_GROUP}" "${DATA_DIR}"
    chmod 0750 "${DATA_DIR}"
}

copy_application_files() {
    log "Copying application files to ${INSTALL_DIR}."
    rsync -a \
        --exclude '.git/' \
        --exclude '.venv/' \
        --exclude 'frontend/node_modules/' \
        --exclude 'frontend/dist/' \
        --exclude 'backend/staticfiles/' \
        "${REPO_ROOT}/" "${INSTALL_DIR}/"
    chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}"
}

validate_no_duckdb_files() {
    log "Checking for DuckDB files in the installed application."
    if find "${INSTALL_DIR}" -iname '*duckdb*' -o -iname '*duck.db*' | grep -q .; then
        fail "DuckDB files were found under ${INSTALL_DIR}; remove them before deployment."
    fi
}
