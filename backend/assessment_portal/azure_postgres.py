import os
from functools import lru_cache

from azure.identity import ManagedIdentityCredential
from django.core.exceptions import ImproperlyConfigured


POSTGRES_TOKEN_SCOPE = os.environ.get(
    "AZURE_POSTGRES_TOKEN_SCOPE",
    "https://ossrdbms-aad.database.windows.net/.default",
)

LOCAL_POSTGRES_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


def validate_remote_postgres_host(host):
    normalized_host = (host or "").strip().lower()
    if normalized_host in LOCAL_POSTGRES_HOSTS:
        raise ImproperlyConfigured(
            "POSTGRES_HOST must point to a remote Azure Database for PostgreSQL host. "
            "Local PostgreSQL hosts are not supported."
        )


@lru_cache(maxsize=1)
def get_managed_identity_credential():
    client_id = os.environ.get("AZURE_CLIENT_ID") or os.environ.get("AZURE_MANAGED_IDENTITY_CLIENT_ID")
    if client_id:
        return ManagedIdentityCredential(client_id=client_id)
    return ManagedIdentityCredential()


def get_postgres_access_token():
    return get_managed_identity_credential().get_token(POSTGRES_TOKEN_SCOPE).token
