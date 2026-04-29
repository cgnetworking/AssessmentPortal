#!/usr/bin/env bash

write_environment_file() {
    if [[ -f "${ENV_FILE}" ]]; then
        log "Environment file already exists at ${ENV_FILE}; leaving it unchanged."
    else
        log "Creating environment file at ${ENV_FILE}."
        install -m 0640 -o root -g "${APP_GROUP}" "${INSTALL_DIR}/deploy/env/assessmentportal.env.example" "${ENV_FILE}"
        sed -i "s|assessment.example.com|${DOMAIN}|g" "${ENV_FILE}"
    fi

    chown root:"${APP_GROUP}" "${ENV_FILE}"
    chmod 0640 "${ENV_FILE}"
}

install_systemd_units() {
    log "Installing systemd units."
    install -m 0644 "${INSTALL_DIR}/deploy/systemd/assessmentportal-gunicorn.service" /etc/systemd/system/assessmentportal-gunicorn.service
    install -m 0644 "${INSTALL_DIR}/deploy/systemd/assessmentportal-worker.service" /etc/systemd/system/assessmentportal-worker.service
    systemctl daemon-reload
}

certificate_subject_alt_name() {
    local host="${DOMAIN}"
    host="${host#[}"
    host="${host%]}"

    if [[ "${host}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ || "${host}" == *:* ]]; then
        printf 'IP:%s' "${host}"
    else
        printf 'DNS:%s' "${host}"
    fi
}

generate_self_signed_certificate() {
    local cert_dir="/etc/letsencrypt/live/${DOMAIN}"
    local cert="${cert_dir}/fullchain.pem"
    local cert_key="${cert_dir}/privkey.pem"
    local san

    if [[ "${GENERATE_SELF_SIGNED_CERT}" -eq 0 ]]; then
        return
    fi

    if [[ -f "${cert}" && -f "${cert_key}" ]]; then
        log "TLS certificate already exists at ${cert_dir}; leaving it unchanged."
        return
    fi

    log "Generating self-signed TLS certificate for ${DOMAIN}."
    san="$(certificate_subject_alt_name)"
    install -d -m 0755 "${cert_dir}"
    openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
        -keyout "${cert_key}" \
        -out "${cert}" \
        -subj "/CN=${DOMAIN}" \
        -addext "subjectAltName=${san}"
    chown root:root "${cert}" "${cert_key}"
    chmod 0644 "${cert}"
    chmod 0600 "${cert_key}"
}

configure_nginx() {
    if [[ "${CONFIGURE_NGINX}" -eq 0 ]]; then
        log "Skipping NGINX configuration."
        return
    fi

    log "Installing NGINX site configuration."
    local available="/etc/nginx/sites-available/assessmentportal.conf"
    local enabled="/etc/nginx/sites-enabled/assessmentportal.conf"
    local cert="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
    local cert_key="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
    local tmp
    tmp="$(mktemp)"
    sed "s|assessment.example.com|${DOMAIN}|g" "${INSTALL_DIR}/deploy/nginx/assessmentportal.conf" > "${tmp}"
    install -m 0644 "${tmp}" "${available}"
    rm -f "${tmp}"
    generate_self_signed_certificate

    if [[ -f "${cert}" && -f "${cert_key}" ]]; then
        ln -sfn "${available}" "${enabled}"
        nginx -t
        systemctl reload nginx
        log "NGINX site enabled and reloaded."
    else
        log "NGINX config installed but not enabled because the Let's Encrypt certificate files do not exist for ${DOMAIN}."
        log "After issuing the cert, enable it with: ln -s ${available} ${enabled} && nginx -t && systemctl reload nginx"
    fi
}

start_services() {
    if [[ "${START_SERVICES}" -eq 0 ]]; then
        log "Skipping service start."
        return
    fi

    if env_has_placeholders; then
        log "Skipping service start because ${ENV_FILE} still contains placeholders."
        return
    fi

    log "Enabling and starting systemd services."
    systemctl enable --now assessmentportal-gunicorn assessmentportal-worker
}
