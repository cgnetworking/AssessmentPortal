def tenant_to_dict(tenant):
    return {
        "id": str(tenant.id),
        "displayName": tenant.display_name,
        "tenantId": tenant.tenant_id,
        "clientId": tenant.client_id,
        "certificateThumbprint": tenant.certificate_thumbprint,
        "keyVaultCertificateUri": tenant.key_vault_certificate_uri,
        "exchangeOrganization": tenant.exchange_organization,
        "sharePointAdminUrl": tenant.sharepoint_admin_url,
        "enabledConnectors": tenant.enabled_connectors,
        "createdAt": tenant.created_at.isoformat(),
        "updatedAt": tenant.updated_at.isoformat(),
    }


def run_to_dict(run):
    return {
        "id": str(run.id),
        "tenantProfileId": str(run.tenant_profile_id),
        "status": run.status,
        "pillar": run.pillar,
        "startedAt": run.started_at.isoformat() if run.started_at else None,
        "completedAt": run.completed_at.isoformat() if run.completed_at else None,
        "exitCode": run.exit_code,
        "errorMessage": run.error_message,
        "outputPath": run.output_path,
        "createdAt": run.created_at.isoformat(),
        "updatedAt": run.updated_at.isoformat(),
    }


def log_to_dict(log):
    return {
        "id": log.id,
        "runId": str(log.run_id),
        "stream": log.stream,
        "message": log.message,
        "createdAt": log.created_at.isoformat(),
    }
