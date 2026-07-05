from __future__ import annotations

from second_brain.config import load_config


def main() -> int:
    config = load_config()
    print(f"Second Brain Core config OK ({config.app_env})")
    print(f"Vault: {config.vault_path}")
    print(f"Database: {config.database_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

