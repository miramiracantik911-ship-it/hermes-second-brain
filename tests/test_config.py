from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from second_brain.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_development_config_loads_with_fixture_vault(self):
        config = load_config(env={}, env_file=".env.example", project_root=ROOT)
        self.assertEqual(config.app_env, "development")
        self.assertEqual(config.vault_path.name, "vault")
        self.assertEqual(config.database_path.name, "second_brain.dev.db")

    def test_production_rejects_default_token(self):
        env = {
            "APP_ENV": "production",
            "AUTHORIZED_TELEGRAM_USER_IDS": "123",
            "VAULT_PATH": "tests/fixtures/vault",
            "DATABASE_URL": "sqlite:///./data/prod.db",
            "ATTACHMENT_TEMP_DIR": "./data/tmp/attachments",
            "LOG_LEVEL": "INFO",
            "HERMES_INTERNAL_TOOL_TOKEN": "dev-token-change-me",
        }
        with self.assertRaisesRegex(ConfigError, "HERMES_INTERNAL_TOOL_TOKEN"):
            load_config(env=env, env_file=None, project_root=ROOT)

    def test_gateway_enabled_requires_token_and_allowlist(self):
        env = {
            "APP_ENV": "development",
            "VAULT_PATH": "tests/fixtures/vault",
            "DATABASE_URL": "sqlite:///./data/gateway-test.db",
            "ATTACHMENT_TEMP_DIR": "./data/tmp/attachments",
            "LOG_LEVEL": "INFO",
            "HERMES_INTERNAL_TOOL_TOKEN": "dev-token-change-me",
            "HERMES_GATEWAY_ENABLED": "true",
        }
        with self.assertRaisesRegex(ConfigError, "TELEGRAM_BOT_TOKEN"):
            load_config(env=env, env_file=None, project_root=ROOT)

    def test_gateway_enabled_accepts_token_and_allowlist(self):
        env = {
            "APP_ENV": "development",
            "VAULT_PATH": "tests/fixtures/vault",
            "DATABASE_URL": "sqlite:///./data/gateway-test.db",
            "ATTACHMENT_TEMP_DIR": "./data/tmp/attachments",
            "LOG_LEVEL": "INFO",
            "HERMES_INTERNAL_TOOL_TOKEN": "dev-token-change-me",
            "HERMES_GATEWAY_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "123:fake",
            "HERMES_GATEWAY_ALLOWED_USER_IDS": "111,222",
        }
        config = load_config(env=env, env_file=None, project_root=ROOT)
        self.assertTrue(config.hermes_gateway_enabled)
        self.assertEqual(config.hermes_gateway_allowed_user_ids, ("111", "222"))


if __name__ == "__main__":
    unittest.main()
