from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from second_brain.config import load_config
from second_brain.db.migrate import apply_migrations, connect
from second_brain.tools.dispatcher import LocalToolDispatcher


def _git(args, cwd):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True
    )


def _git_available() -> bool:
    try:
        return subprocess.run(
            ["git", "--version"], capture_output=True
        ).returncode == 0
    except FileNotFoundError:
        return False


@unittest.skipUnless(_git_available(), "git not available")
class GitSyncCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sb-gitsync-"))
        self.remote = self.tmp / "remote.git"
        _git(["init", "--bare", "-b", "main", str(self.remote)], self.tmp)

        self.vault = self.tmp / "vault"
        (self.vault / "00 Inbox").mkdir(parents=True)
        _git(["init", "-b", "main"], self.vault)
        _git(["config", "user.email", "t@example.com"], self.vault)
        _git(["config", "user.name", "Tester"], self.vault)
        (self.vault / "README.md").write_text("inbox", encoding="utf-8")
        _git(["add", "-A"], self.vault)
        _git(["commit", "-m", "init"], self.vault)
        _git(["remote", "add", "origin", str(self.remote)], self.vault)
        _git(["push", "-u", "origin", "main"], self.vault)

        self.db_path = self.tmp / "g.db"
        env = {
            "APP_ENV": "test",
            "VAULT_PATH": str(self.vault),
            "DATABASE_URL": f"sqlite:///{self.db_path}",
            "ATTACHMENT_TEMP_DIR": str(self.tmp / "att"),
            "LOG_LEVEL": "INFO",
            "HERMES_INTERNAL_TOOL_TOKEN": "test-token",
            "VAULT_GIT_SYNC": "true",
        }
        self.config = load_config(env=env, env_file=None, project_root=ROOT)
        apply_migrations(self.config)
        self.conn = connect(self.config)
        self.dispatcher = LocalToolDispatcher(self.conn, self.config)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_capture_commits_and_pushes(self):
        res = self.dispatcher.call(
            "capture_note", {"text": "sinkron ke git"}, user_id="t:1"
        )
        self.assertTrue(res.ok, res.error)
        self.assertTrue(res.result["synced"])

        local_log = _git(["log", "--oneline"], self.vault).stdout
        self.assertIn("capture:", local_log)
        remote_log = _git(["log", "--oneline", "origin/main"], self.vault).stdout
        self.assertIn("capture:", remote_log)

    def test_undo_commits_deletion(self):
        res = self.dispatcher.call(
            "capture_note", {"text": "akan diundo dan dicommit"}, user_id="t:1"
        )
        note_path = res.result["note_path"]
        self.dispatcher.call("undo_operation", {"operation_id": res.operation_id})

        self.assertFalse((self.vault / note_path).exists())
        local_log = _git(["log", "--oneline"], self.vault).stdout
        self.assertIn("undo:", local_log)


if __name__ == "__main__":
    unittest.main()
