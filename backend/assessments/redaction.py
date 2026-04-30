import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


REDACTED = "[REDACTED]"
REDACTED_EMAIL = "[REDACTED_EMAIL]"
REDACTED_PATH = "[REDACTED_PATH]"

SENSITIVE_KEY_NAMES = {
    "accesstoken",
    "apikey",
    "authorization",
    "clientassertion",
    "clientsecret",
    "code",
    "credential",
    "identityheader",
    "idtoken",
    "keyvaultcertificateuri",
    "password",
    "pwd",
    "refreshtoken",
    "sas",
    "secret",
    "sig",
    "signature",
    "state",
    "token",
    "xidentityheader",
}

URL_RE = re.compile(r"https?://[^\s\"'<>()]+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
AUTHORIZATION_RE = re.compile(r"(?i)(\bauthorization\s*[:=]\s*)(?:bearer\s+)?[A-Za-z0-9._~+/=-]+")
BEARER_RE = re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]+")
KEY_VALUE_RE = re.compile(
    r"(?i)([\"']?(?:access_token|api_key|apikey|client_assertion|client_secret|code|credential|"
    r"identity_header|id_token|password|pwd|refresh_token|secret|sig|signature|state|token|x-identity-header)"
    r"[\"']?\s*[:=]\s*[\"']?)([^\"',\s;&}]+)"
)
UNIX_PATH_RE = re.compile(r"(?<!:)\/(?:Users|home|opt|private|tmp|var|etc|run|Volumes)\/[^\s\"'<>]+")
WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:\\[^\s\"'<>]+")


def _normalise_key(key):
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def is_sensitive_key(key):
    normalised = _normalise_key(key)
    if normalised in SENSITIVE_KEY_NAMES:
        return True
    return normalised.endswith(("secret", "token", "password", "credential"))


def _redact_query(query):
    if not query:
        return query
    pairs = parse_qsl(query, keep_blank_values=True)
    return urlencode([(key, REDACTED if is_sensitive_key(key) else value) for key, value in pairs])


def _redact_url(match):
    raw_url = match.group(0)
    trailing = ""
    while raw_url and raw_url[-1] in ".,;":
        trailing = raw_url[-1] + trailing
        raw_url = raw_url[:-1]

    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return REDACTED + trailing

    netloc = parsed.netloc
    if parsed.username or parsed.password:
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        netloc = f"{REDACTED}@{host}{port}"

    path = parsed.path
    if parsed.hostname and parsed.hostname.lower().endswith(".vault.azure.net"):
        netloc = "[REDACTED_VAULT].vault.azure.net"
        parts = [part for part in parsed.path.split("/") if part]
        if parts and parts[0] in {"certificates", "secrets"}:
            path = f"/{parts[0]}/{REDACTED}"

    query = _redact_query(parsed.query)
    fragment = _redact_query(parsed.fragment)
    return urlunsplit((parsed.scheme, netloc, path, query, fragment)) + trailing


def redact_sensitive_text(value):
    if value is None:
        return ""

    text = str(value)
    text = URL_RE.sub(_redact_url, text)
    text = AUTHORIZATION_RE.sub(r"\1" + REDACTED, text)
    text = BEARER_RE.sub(r"\1" + REDACTED, text)
    text = KEY_VALUE_RE.sub(r"\1" + REDACTED, text)
    text = EMAIL_RE.sub(REDACTED_EMAIL, text)
    text = UNIX_PATH_RE.sub(REDACTED_PATH, text)
    text = WINDOWS_PATH_RE.sub(REDACTED_PATH, text)
    return text


def redact_sensitive_data(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            redacted[key] = REDACTED if is_sensitive_key(key) else redact_sensitive_data(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, str):
        return redact_sensitive_text(value)
    return value
