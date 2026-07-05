from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
import shutil
import subprocess

from second_brain.config import AppConfig
from second_brain.tools.capabilities import CapabilityError, require_enabled
from second_brain.tools.dispatcher import LocalToolDispatcher


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str


@dataclass(frozen=True)
class Phase1BPreflight:
    checks: tuple[CheckResult, ...]

    @property
    def ready_for_live_gateway(self) -> bool:
        return all(check.ok for check in self.checks)

    def to_markdown(self) -> str:
        lines = [
            "# Phase 1B Preflight",
            "",
            f"Ready for live gateway: `{str(self.ready_for_live_gateway).lower()}`",
            "",
            "| Check | Status | Message |",
            "| --- | --- | --- |",
        ]
        for check in self.checks:
            status = "ok" if check.ok else "blocked"
            lines.append(f"| {check.name} | {status} | {check.message} |")
        return "\n".join(lines) + "\n"


def _check_hermes_installed() -> CheckResult:
    hermes_path = shutil.which("hermes")
    if not hermes_path:
        return CheckResult(
            name="hermes_installed",
            ok=False,
            message="`hermes` command was not found in PATH.",
        )

    try:
        completed = subprocess.run(
            [hermes_path, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:  # pragma: no cover - defensive for local machines
        return CheckResult(
            name="hermes_installed",
            ok=False,
            message=f"`hermes --version` failed: {exc}",
        )

    version = (completed.stdout or completed.stderr).strip() or "version unknown"
    return CheckResult(
        name="hermes_installed",
        ok=completed.returncode == 0,
        message=f"{hermes_path} ({version})",
    )


def run_phase1b_preflight(config: AppConfig, dispatcher: LocalToolDispatcher) -> Phase1BPreflight:
    checks: list[CheckResult] = []
    checks.append(_check_hermes_installed())

    checks.append(
        CheckResult(
            name="gateway_enabled",
            ok=config.hermes_gateway_enabled,
            message="HERMES_GATEWAY_ENABLED is true."
            if config.hermes_gateway_enabled
            else "HERMES_GATEWAY_ENABLED is false.",
        )
    )
    checks.append(
        CheckResult(
            name="telegram_token_present",
            ok=bool(config.telegram_bot_token),
            message="Telegram token is present in local config."
            if config.telegram_bot_token
            else "TELEGRAM_BOT_TOKEN is missing.",
        )
    )
    checks.append(
        CheckResult(
            name="telegram_allowlist_present",
            ok=bool(config.hermes_gateway_allowed_user_ids),
            message=f"{len(config.hermes_gateway_allowed_user_ids)} allowed user id(s) configured."
            if config.hermes_gateway_allowed_user_ids
            else "HERMES_GATEWAY_ALLOWED_USER_IDS is missing.",
        )
    )

    core_host = urlparse(config.second_brain_core_url).hostname or ""
    core_local = core_host in {"127.0.0.1", "localhost", "::1"}
    checks.append(
        CheckResult(
            name="core_url_local",
            ok=core_local,
            message=f"SECOND_BRAIN_CORE_URL is local-only ({core_host})."
            if core_local
            else f"SECOND_BRAIN_CORE_URL must stay loopback, got '{core_host}'.",
        )
    )

    for capability_id in ("health_check", "job_status", "sync_status"):
        try:
            require_enabled(dispatcher.conn, capability_id)
        except CapabilityError as exc:
            checks.append(
                CheckResult(
                    name=f"capability_{capability_id}",
                    ok=False,
                    message=str(exc),
                )
            )
        else:
            checks.append(
                CheckResult(
                    name=f"capability_{capability_id}",
                    ok=True,
                    message="Capability is enabled.",
                )
            )

    health = dispatcher.call("health_check", user_id="local:preflight")
    checks.append(
        CheckResult(
            name="health_check_tool",
            ok=health.ok,
            message="health_check succeeded."
            if health.ok
            else health.error.get("message", "health_check failed."),
        )
    )

    # Capture/search/move/update are enabled (Phase 2-3); assert a later-phase
    # tool is still disabled so the capability gate is proven to reject early tools.
    future = dispatcher.call("approve_media", user_id="local:preflight")
    checks.append(
        CheckResult(
            name="future_write_tools_disabled",
            ok=not future.ok and future.error is not None,
            message="approve_media is disabled as expected."
            if not future.ok
            else "approve_media unexpectedly succeeded.",
        )
    )

    return Phase1BPreflight(checks=tuple(checks))
