from __future__ import annotations

from second_brain.config import load_config
from second_brain.db.migrate import apply_migrations, connect
from second_brain.tools.dispatcher import LocalToolDispatcher
from second_brain.tools.preflight import run_phase1b_preflight


def main() -> int:
    config = load_config()
    apply_migrations(config)
    with connect(config) as conn:
        report = run_phase1b_preflight(config, LocalToolDispatcher(conn, config))
    print(report.to_markdown())
    return 0 if report.ready_for_live_gateway else 1


if __name__ == "__main__":
    raise SystemExit(main())
