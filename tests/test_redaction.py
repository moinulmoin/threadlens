"""Unit tests for display-time redaction helpers in cli.py."""
import unittest

from threadlens import cli


class RedactSecretsTests(unittest.TestCase):
    # ── explicit token shapes ────────────────────────────────────────────────

    def test_redacts_phc_token(self):
        token = "phc_" + "A" * 16
        result = cli.redact_secrets(f"sent token {token} here")
        self.assertNotIn("phc_", result)
        self.assertIn(cli.REDACTION, result)

    def test_redacts_sk_token(self):
        token = "sk-aBcDeFgHiJkLmNoPqRs"
        result = cli.redact_secrets(f"key={token}")
        self.assertNotIn("sk-", result)
        self.assertIn(cli.REDACTION, result)

    def test_redacts_ghp_token(self):
        token = "ghp_" + "A" * 20
        result = cli.redact_secrets(f"auth: {token}")
        self.assertNotIn("ghp_", result)
        self.assertIn(cli.REDACTION, result)

    def test_redacts_xoxb_token(self):
        token = "xoxb-abc123def456"
        result = cli.redact_secrets(f"slack token {token}")
        self.assertNotIn("xoxb-", result)
        self.assertIn(cli.REDACTION, result)

    def test_redacts_akia_token(self):
        token = "AKIAIOSFODNN7EXAMPLE"
        result = cli.redact_secrets(f"aws key {token} used")
        self.assertNotIn("AKIA", result)
        self.assertIn(cli.REDACTION, result)

    def test_redacts_aiza_token(self):
        token = "AIza" + "A1b2C3d4E5f6G7h8I9j0K1l2m3n4o5p"
        result = cli.redact_secrets(f"gcp key {token}")
        self.assertNotIn("AIza", result)
        self.assertIn(cli.REDACTION, result)

    def test_redacts_jwt(self):
        token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        result = cli.redact_secrets(f"token {token}")
        self.assertNotIn("eyJ", result)
        self.assertIn(cli.REDACTION, result)

    def test_redacts_bearer_token(self):
        token = "Bearer abcDefGhiJklMnoPqrStuVwxYz1234567890"
        result = cli.redact_secrets(f"Authorization: {token}")
        self.assertNotIn("abcDefGhiJklMnoPqrStuVwxYz1234567890", result)
        self.assertIn("Bearer", result)
        self.assertIn(cli.REDACTION, result)

    def test_redacts_api_key_value_but_keeps_label(self):
        text = "api_key=supersecretvalue123"
        result = cli.redact_secrets(text)
        self.assertIn("api_key", result)
        self.assertNotIn("supersecretvalue123", result)
        self.assertIn(cli.REDACTION, result)

    # ── false-positive guards ────────────────────────────────────────────────

    def test_does_not_redact_40char_hex_sha(self):
        sha = "a" * 40
        result = cli.redact_secrets(f"commit {sha} landed")
        self.assertIn(sha, result)
        self.assertNotIn(cli.REDACTION, result)

    def test_does_not_redact_git_branch_name(self):
        text = "feature/add-otp-login"
        result = cli.redact_secrets(text)
        self.assertIn(text, result)
        self.assertNotIn(cli.REDACTION, result)

    def test_does_not_redact_normal_prose(self):
        text = "Fix the webhook retry bug in billing service"
        result = cli.redact_secrets(text)
        self.assertEqual(result, text)

    def test_redaction_sentinel_uses_angle_quote_glyphs(self):
        # Pin the exact sentinel so an escape typo (e.g. U+203C/U+203E) is caught.
        self.assertEqual(cli.REDACTION, "‹redacted›")


class SanitizeTitleTests(unittest.TestCase):
    def test_collapses_whitespace(self):
        result = cli.sanitize_title("hello   world\t\nnow")
        self.assertEqual(result, "hello world now")

    def test_truncates_at_80_with_ellipsis(self):
        long_title = "A" * 90
        result = cli.sanitize_title(long_title)
        self.assertEqual(len(result), 80)
        self.assertTrue(result.endswith("…"))

    def test_no_truncation_at_exactly_80(self):
        title = "A" * 80
        result = cli.sanitize_title(title)
        self.assertEqual(result, title)
        self.assertFalse(result.endswith("…"))

    def test_redacts_token_embedded_in_title(self):
        token = "phc_" + "B" * 16
        title = f"Session with token {token} inside"
        result = cli.sanitize_title(title)
        self.assertNotIn("phc_", result)
        self.assertIn(cli.REDACTION, result)

    def test_empty_string(self):
        self.assertEqual(cli.sanitize_title(""), "")

    def test_none_like_empty(self):
        # sanitize_title calls redact_secrets(raw or "")
        self.assertEqual(cli.sanitize_title(""), "")


class PresentableResultTests(unittest.TestCase):
    def _result(self, **over):
        base = {
            "source": "codex",
            "session_id": "s1",
            "cwd": "/tmp/p",
            "source_path": "/tmp/p/t.jsonl",
            "source_line": 1,
            "title": "ok",
            "best_snippets": [],
            "matched_terms": [],
            "score": 1.0,
        }
        base.update(over)
        return base

    def test_redacts_matched_terms_but_keeps_benign(self):
        token = "phc_" + "A" * 16
        payload = cli.presentable_result(self._result(matched_terms=["plunk", token]), None)
        self.assertIn("plunk", payload["matched_terms"])
        self.assertNotIn(token, payload["matched_terms"])
        self.assertIn(cli.REDACTION, payload["matched_terms"])

    def test_redacts_title_and_snippets(self):
        token = "phc_" + "B" * 16
        payload = cli.presentable_result(
            self._result(
                title=f"session {token}",
                best_snippets=[{"role": "user", "timestamp": "t", "snippet": f"ctx {token}"}],
            ),
            None,
        )
        self.assertNotIn(token, payload["title"])
        self.assertNotIn(token, payload["best_snippets"][0]["snippet"])

    def test_does_not_mutate_original_result(self):
        token = "phc_" + "C" * 16
        result = self._result(title=f"t {token}", matched_terms=[token])
        cli.presentable_result(result, None)
        self.assertIn(token, result["title"])
        self.assertIn(token, result["matched_terms"])


if __name__ == "__main__":
    unittest.main()
