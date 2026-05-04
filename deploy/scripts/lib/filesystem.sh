#!/usr/bin/env bash

ensure_users_and_directories() {
    log "Creating application user, groups, and directories."

    if ! getent group "${APP_GROUP}" >/dev/null; then
        groupadd --system "${APP_GROUP}"
    fi

    if ! id "${APP_USER}" >/dev/null 2>&1; then
        useradd --system --gid "${APP_GROUP}" --home-dir "${DATA_DIR}" --create-home --shell /usr/sbin/nologin "${APP_USER}"
    fi

    install -d -m 0755 -o root -g root "${INSTALL_DIR}" "${ENV_DIR}"
    install -d -m 0750 -o "${APP_USER}" -g "${APP_GROUP}" \
        "${DATA_DIR}" \
        "${DATA_DIR}/assessment-work" \
        "${DATA_DIR}/.cache" \
        "${DATA_DIR}/.config" \
        "${DATA_DIR}/.local" \
        "${DATA_DIR}/.local/share" \
        "${DATA_DIR}/.local/share/powershell" \
        "${DATA_DIR}/.local/share/powershell/Scripts" \
        "${DATA_DIR}/.local/share/powershell/Modules"
    chown -R "${APP_USER}:${APP_GROUP}" "${DATA_DIR}"
    chmod 0750 "${DATA_DIR}" "${DATA_DIR}/assessment-work" "${DATA_DIR}/.cache" "${DATA_DIR}/.config" "${DATA_DIR}/.local"
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
    lock_application_files
}

prepare_build_write_paths() {
    log "Preparing application build output directories."

    install -d -m 0750 -o "${APP_USER}" -g "${APP_GROUP}" \
        "${INSTALL_DIR}/.venv" \
        "${INSTALL_DIR}/frontend" \
        "${INSTALL_DIR}/frontend/node_modules" \
        "${INSTALL_DIR}/frontend/dist" \
        "${INSTALL_DIR}/backend/staticfiles"
    chown -R "${APP_USER}:${APP_GROUP}" \
        "${INSTALL_DIR}/.venv" \
        "${INSTALL_DIR}/frontend" \
        "${INSTALL_DIR}/backend/staticfiles"
}

lock_application_files() {
    log "Locking deployed application files to root ownership."

    chown -R root:root "${INSTALL_DIR}"
    find "${INSTALL_DIR}" -type d -exec chmod u=rwx,go=rx {} +
    find "${INSTALL_DIR}" -type f -perm /111 -exec chmod u=rwx,go=rx {} +
    find "${INSTALL_DIR}" -type f ! -perm /111 -exec chmod u=rw,go=r {} +
    chown -R "${APP_USER}:${APP_GROUP}" "${DATA_DIR}"
    chmod 0750 "${DATA_DIR}" "${DATA_DIR}/assessment-work" "${DATA_DIR}/.cache" "${DATA_DIR}/.config" "${DATA_DIR}/.local"
}

validate_no_duckdb_files() {
    log "Checking for DuckDB files in the installed application."
    if find "${INSTALL_DIR}" -iname '*duckdb*' -o -iname '*duck.db*' | grep -q .; then
        fail "DuckDB files were found under ${INSTALL_DIR}; remove them before deployment."
    fi
}
