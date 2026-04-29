from urllib.parse import urlparse

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


class KeyVaultCertificateProvider:
    def __init__(self, credential=None):
        self.credential = credential or DefaultAzureCredential()

    def get_pfx_base64(self, certificate_uri: str) -> str:
        parsed = urlparse(certificate_uri)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Key Vault certificate URI is required")

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2 or parts[0].lower() not in {"certificates", "secrets"}:
            raise ValueError("Key Vault URI must target a certificate or secret")

        secret_name = parts[1]
        version = parts[2] if len(parts) > 2 else None
        vault_url = f"{parsed.scheme}://{parsed.netloc}"
        client = SecretClient(vault_url=vault_url, credential=self.credential)
        secret = client.get_secret(secret_name, version)
        return secret.value
