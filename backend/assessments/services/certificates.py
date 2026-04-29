import base64
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

from azure.identity import ManagedIdentityCredential
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError


KEY_VAULT_API_VERSION = "7.5"
KEY_VAULT_SCOPE = "https://vault.azure.net/.default"


@dataclass(frozen=True)
class CreatedCertificate:
    certificate_thumbprint: str
    key_vault_certificate_uri: str


@dataclass(frozen=True)
class KeyVaultSecretRef:
    name: str
    version: Optional[str]


@dataclass(frozen=True)
class KeyVaultCertificateRef:
    name: str
    version: Optional[str]


def create_certificate_for_tenant(tenant) -> CreatedCertificate:
    vault_url = _resolve_vault_url(tenant.key_vault_certificate_uri)
    name = _certificate_name(tenant)
    cert, pfx_base64 = _generate_certificate(tenant)

    certificate = _key_vault_request(
        "POST",
        vault_url,
        f"/certificates/{name}/import",
        json={
            "value": pfx_base64,
            "policy": {
                "key_props": {
                    "exportable": True,
                    "kty": "RSA",
                    "key_size": 2048,
                    "reuse_key": False,
                },
                "secret_props": {
                    "contentType": "application/x-pkcs12",
                },
                "issuer": {
                    "name": "Unknown",
                },
            },
            "tags": {
                "tenantProfileId": str(tenant.id),
                "tenantId": tenant.tenant_id,
                "clientId": tenant.client_id,
                "managedBy": "AssessmentPortal",
            },
        },
    )
    certificate_id = certificate.get("id")
    if not certificate_id:
        raise ValidationError("Key Vault did not return a certificate URI.")

    return CreatedCertificate(
        certificate_thumbprint=_thumbprint(cert),
        key_vault_certificate_uri=certificate_id,
    )


def get_public_certificate_der(tenant) -> bytes:
    vault_url = _resolve_vault_url(tenant.key_vault_certificate_uri)
    parsed = urlparse(tenant.key_vault_certificate_uri)
    parts = [part for part in parsed.path.split("/") if part]
    if parts and parts[0] == "certificates":
        certificate_ref = _certificate_ref_from_uri(tenant.key_vault_certificate_uri)
        path = f"/certificates/{certificate_ref.name}"
        if certificate_ref.version:
            path = f"{path}/{certificate_ref.version}"
        certificate = _key_vault_request("GET", vault_url, path)
        cer = certificate.get("cer")
        if not cer:
            raise ValidationError("The Key Vault certificate did not contain public certificate material.")
        return base64.b64decode(cer)

    secret_ref = _secret_ref_from_uri(tenant.key_vault_certificate_uri)
    path = f"/secrets/{secret_ref.name}"
    if secret_ref.version:
        path = f"{path}/{secret_ref.version}"
    secret = _key_vault_request("GET", vault_url, path)
    pfx_bytes = base64.b64decode(secret.get("value", ""))
    _, cert, _ = pkcs12.load_key_and_certificates(pfx_bytes, None)
    if cert is None:
        raise ValidationError("The Key Vault secret did not contain a certificate.")
    return cert.public_bytes(serialization.Encoding.DER)


def _key_vault_request(method, vault_url, path, **kwargs):
    token = ManagedIdentityCredential().get_token(KEY_VAULT_SCOPE).token
    response = requests.request(
        method,
        f"{vault_url}{path}",
        params={"api-version": KEY_VAULT_API_VERSION},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        **kwargs,
    )
    if response.ok:
        return response.json()

    try:
        payload = response.json()
        message = payload.get("error", {}).get("message") or payload.get("error", {}).get("code")
    except ValueError:
        message = response.text
    raise ValidationError(f"Key Vault request failed ({response.status_code}): {message}")


def _generate_certificate(tenant):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, _subject_common_name(tenant)),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .sign(key, hashes.SHA256())
    )
    pfx = pkcs12.serialize_key_and_certificates(
        name=_subject_common_name(tenant).encode("utf-8"),
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert, base64.b64encode(pfx).decode("ascii")


def _resolve_vault_url(existing_uri):
    if existing_uri:
        parsed = urlparse(existing_uri)
        if parsed.scheme == "https" and parsed.netloc.endswith(".vault.azure.net"):
            return f"{parsed.scheme}://{parsed.netloc}"

    if settings.ZTA_KEY_VAULT_URL:
        parsed = urlparse(settings.ZTA_KEY_VAULT_URL)
        if parsed.scheme == "https" and parsed.netloc.endswith(".vault.azure.net"):
            return settings.ZTA_KEY_VAULT_URL

    raise ImproperlyConfigured("ZTA_KEY_VAULT_URL must be set to an Azure Key Vault URL.")


def _secret_ref_from_uri(uri):
    parsed = urlparse(uri)
    if parsed.scheme != "https" or not parsed.netloc.endswith(".vault.azure.net"):
        raise ValidationError("Tenant does not have a valid Key Vault certificate URI.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] not in {"secrets", "certificates"}:
        raise ValidationError("Tenant Key Vault URI must target a secret or certificate.")
    return KeyVaultSecretRef(name=parts[1], version=parts[2] if len(parts) > 2 else None)


def _certificate_ref_from_uri(uri):
    parsed = urlparse(uri)
    if parsed.scheme != "https" or not parsed.netloc.endswith(".vault.azure.net"):
        raise ValidationError("Tenant does not have a valid Key Vault certificate URI.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] != "certificates":
        raise ValidationError("Tenant Key Vault URI must target a certificate.")
    return KeyVaultCertificateRef(name=parts[1], version=parts[2] if len(parts) > 2 else None)


def _certificate_name(tenant):
    base = re.sub(r"[^a-zA-Z0-9-]+", "-", tenant.display_name.strip()).strip("-").lower()
    if not base:
        base = "tenant"
    base = base[:48].strip("-") or "tenant"
    return f"zta-{base}-{str(tenant.id)[:8]}"


def _subject_common_name(tenant):
    name = tenant.display_name.strip() or tenant.tenant_id
    return f"ZeroTrustAssessment {name}"[:64]


def _thumbprint(cert):
    return cert.fingerprint(hashes.SHA1()).hex().upper()
