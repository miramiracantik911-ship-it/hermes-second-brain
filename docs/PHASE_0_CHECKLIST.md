# Phase 0 Checklist

## Safety Boundary

- [x] Production vault is not connected.
- [x] Development uses fake vault fixture.
- [x] No real secrets are stored in repo.
- [ ] Real vault audit only runs after Andri provides a read-only copy.

## Repo Foundation

- [x] Repository skeleton created.
- [x] `.env.example` created.
- [x] README created.
- [x] Documentation handoff files created.

## Config

- [x] Config loader created.
- [x] Development config validation created.
- [x] Unsafe production config validation created.

## Database

- [x] Migration runner created.
- [x] Initial SQLite schema created.
- [x] WAL mode enabled by migration runner.

## Fake Vault

- [x] PARA-like fixture structure created.
- [x] Example capture note created.
- [x] Example project note created.
- [x] Example area/resource notes created.
- [x] Example private note created.

## Audit

- [x] Read-only audit module created.
- [x] Fake vault audit test created.
- [x] Fake vault audit report created.
- [ ] Real read-only vault audit report created.

## Verification

- [x] Test suite passes.
- [x] Config command runs.
- [x] Migration command runs.

## Phase 0 Result

- [x] Local Phase 0 foundation is complete.
- [x] No production vault write access was used.
- [x] Programmer/AI handoff documentation is available.
- [ ] Optional real vault audit waits for a read-only vault copy from Andri.
