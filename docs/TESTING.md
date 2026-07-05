# Testing

## Run Tests

```bash
python3 -m unittest discover -s tests
```

Optional if pytest is installed:

```bash
pytest
```

## Current Coverage

- Development config loads from `.env.example`.
- Unsafe production config is rejected.
- Gateway-enabled config requires Telegram token and allowlist.
- SQLite migration creates Phase 0 tables.
- Initial capabilities are seeded.
- Disabled capabilities are rejected.
- `health_check` dispatch records audit operation.
- Disabled tool calls record rejected audit operation.
- Phase 1B preflight reports blockers when Hermes/credentials are missing.
- Phase 1B preflight can pass with mocked Hermes and gateway config.
- Fake vault audit is read-only.

Latest local verification on 2026-06-16:

```text
Ran 12 tests in 0.044s
OK
```

## Phase 1B Preflight

```bash
PYTHONPATH=src python3 -m second_brain.preflight
```

Current local result is expected to be blocked because Hermes and Telegram credentials are not configured yet.

## Known Gaps

- No Hermes integration yet.
- No Telegram integration yet.
- No write tools yet.
- No real vault audit has been run.
