#!/usr/bin/env bash

create_python_environment() {
    log "Creating Python virtual environment and installing pinned requirements."
    runuser -u "${APP_USER}" -- python3.12 -m venv "${INSTALL_DIR}/.venv"
    runuser -u "${APP_USER}" -- "${INSTALL_DIR}/.venv/bin/pip" install --upgrade "pip==${PIP_VERSION}" "wheel==${WHEEL_VERSION}"
    runuser -u "${APP_USER}" -- "${INSTALL_DIR}/.venv/bin/pip" install --only-binary=:all: -r "${INSTALL_DIR}/requirements.txt"
}

run_django_setup() {
    if [[ "${RUN_MIGRATIONS}" -eq 0 ]]; then
        log "Skipping Django migrate and collectstatic."
        return
    fi

    if env_has_placeholders; then
        log "Skipping Django migrate and collectstatic because ${ENV_FILE} still contains placeholders."
        return
    fi

    log "Running Django migrations and static asset collection."
    load_env_file
    pushd "${INSTALL_DIR}/backend" >/dev/null
    runuser -u "${APP_USER}" -- env HOME="${DATA_DIR}" "${INSTALL_DIR}/.venv/bin/python" manage.py migrate
    runuser -u "${APP_USER}" -- env HOME="${DATA_DIR}" "${INSTALL_DIR}/.venv/bin/python" manage.py collectstatic --noinput
    popd >/dev/null
}
