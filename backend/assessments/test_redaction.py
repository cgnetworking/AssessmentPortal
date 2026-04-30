import unittest

from assessments.redaction import REDACTED, REDACTED_EMAIL, REDACTED_PATH, redact_sensitive_data, redact_sensitive_text


class RedactionTests(unittest.TestCase):
    def test_redacts_sensitive_url_query_values(self):
        text = "GET /auth/complete?code=abc123&state=xyz&tenant=contoso"

        redacted = redact_sensitive_text(text)

        self.assertIn(f"code={REDACTED}", redacted)
        self.assertIn(f"state={REDACTED}", redacted)
        self.assertIn("tenant=contoso", redacted)
        self.assertNotIn("abc123", redacted)
        self.assertNotIn("xyz", redacted)

    def test_redacts_key_vault_secret_uri(self):
        text = "https://prodvault.vault.azure.net/secrets/app-cert/version123?api-version=7.5"

        redacted = redact_sensitive_text(text)

        self.assertIn("[REDACTED_VAULT].vault.azure.net/secrets/[REDACTED]", redacted)
        self.assertNotIn("prodvault", redacted)
        self.assertNotIn("app-cert", redacted)
        self.assertNotIn("version123", redacted)

    def test_redacts_nested_sensitive_keys_and_old_audit_metadata(self):
        metadata = {
            "tenant": {
                "displayName": "contoso",
                "keyVaultCertificateUri": "https://vault.vault.azure.net/certificates/app/123",
                "clientSecret": "super-secret",
            }
        }

        redacted = redact_sensitive_data(metadata)

        self.assertEqual(redacted["tenant"]["displayName"], "contoso")
        self.assertEqual(redacted["tenant"]["keyVaultCertificateUri"], REDACTED)
        self.assertEqual(redacted["tenant"]["clientSecret"], REDACTED)

    def test_redacts_log_pii_paths_and_bearer_tokens(self):
        text = "Authorization: Bearer abc.def user jane.doe@example.com failed in /opt/assessmentportal/backend/app.py"

        redacted = redact_sensitive_text(text)

        self.assertIn(f"Authorization: {REDACTED}", redacted)
        self.assertIn(REDACTED_EMAIL, redacted)
        self.assertIn(REDACTED_PATH, redacted)
        self.assertNotIn("abc.def", redacted)
        self.assertNotIn("jane.doe@example.com", redacted)
        self.assertNotIn("/opt/assessmentportal", redacted)


if __name__ == "__main__":
    unittest.main()
