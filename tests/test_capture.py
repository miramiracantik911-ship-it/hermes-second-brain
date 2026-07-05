from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from second_brain.config import load_config
from second_brain.db.migrate import apply_migrations, connect
from second_brain.tools.dispatcher import LocalToolDispatcher


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sb-capture-"))
        self.vault = self.tmp / "vault"
        shutil.copytree(ROOT / "tests" / "fixtures" / "vault", self.vault)
        self.db_path = self.tmp / "capture.db"
        env = {
            "APP_ENV": "test",
            "VAULT_PATH": str(self.vault),
            "DATABASE_URL": f"sqlite:///{self.db_path}",
            "ATTACHMENT_TEMP_DIR": str(self.tmp / "att"),
            "LOG_LEVEL": "INFO",
            "HERMES_INTERNAL_TOOL_TOKEN": "test-token",
        }
        self.config = load_config(env=env, env_file=None, project_root=ROOT)
        apply_migrations(self.config)
        self.conn = connect(self.config)
        self.dispatcher = LocalToolDispatcher(self.conn, self.config)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _inbox(self):
        return self.vault / "00 Inbox"

    def _capture(self, **payload):
        return self.dispatcher.call("capture_note", payload, user_id="telegram:1")

    def test_capture_creates_note_with_frontmatter(self):
        res = self._capture(text="Belajar spaced repetition tiap pagi", tags=["learning"])
        self.assertTrue(res.ok, res.error)
        note_path = res.result["note_path"]
        self.assertTrue(note_path.startswith("00 Inbox/"))

        content = (self.vault / note_path).read_text(encoding="utf-8")
        self.assertIn("code_stage: capture", content)
        self.assertIn("para: inbox", content)
        self.assertIn("sensitive: false", content)
        self.assertIn("semantic_index: enabled", content)
        self.assertIn("Belajar spaced repetition tiap pagi", content)

        op = self.conn.execute(
            "SELECT undo_payload, target_id, status FROM operations WHERE id = ?",
            (res.operation_id,),
        ).fetchone()
        self.assertEqual(op["status"], "success")
        self.assertEqual(op["target_id"], note_path)
        self.assertIn(note_path, op["undo_payload"])

        note = self.conn.execute(
            "SELECT code_stage, sensitive, semantic_index FROM notes WHERE path = ?",
            (note_path,),
        ).fetchone()
        self.assertEqual(note["code_stage"], "capture")
        self.assertEqual(note["sensitive"], 0)
        self.assertEqual(note["semantic_index"], 1)

    def test_title_derived_from_body(self):
        res = self._capture(text="Ide produk baru untuk toko\nbaris kedua diabaikan")
        content = (self.vault / res.result["note_path"]).read_text(encoding="utf-8")
        self.assertIn('title: "Ide produk baru untuk toko"', content)

    def test_idempotency_dedupes(self):
        payload = {"text": "pesan yang sama persis", "idempotency_key": "msg-42"}
        r1 = self.dispatcher.call("capture_note", dict(payload))
        r2 = self.dispatcher.call("capture_note", dict(payload))
        self.assertEqual(r1.result["note_path"], r2.result["note_path"])
        self.assertFalse(r1.result["deduped"])
        self.assertTrue(r2.result["deduped"])
        count = self.conn.execute(
            "SELECT COUNT(*) AS n FROM notes WHERE path = ?",
            (r1.result["note_path"],),
        ).fetchone()["n"]
        self.assertEqual(count, 1)

    def test_sensitive_note_is_hidden(self):
        res = self._capture(text="ini password bank saya rahasia")
        self.assertTrue(res.result["sensitive"])
        note_path = res.result["note_path"]
        self.assertIn("private-", note_path)
        self.assertNotIn("password", note_path.lower())

        content = (self.vault / note_path).read_text(encoding="utf-8")
        self.assertIn("sensitive: true", content)
        self.assertIn("semantic_index: disabled", content)
        self.assertIn("ai_processing: disabled", content)
        self.assertIn("telegram_preview: disabled", content)

        note = self.conn.execute(
            "SELECT semantic_index, sensitive FROM notes WHERE path = ?",
            (note_path,),
        ).fetchone()
        self.assertEqual(note["semantic_index"], 0)
        self.assertEqual(note["sensitive"], 1)

    def test_path_traversal_in_title_is_contained(self):
        res = self._capture(text="halo", title="../../../etc/passwd")
        note_path = res.result["note_path"]
        self.assertTrue(note_path.startswith("00 Inbox/"))
        abs_path = (self.vault / note_path).resolve()
        self.assertTrue(str(abs_path).startswith(str(self.vault.resolve())))

    def test_no_temp_files_left_behind(self):
        self._capture(text="halo dunia")
        self.assertEqual(list(self._inbox().glob("*.tmp")), [])

    def test_undo_removes_note(self):
        res = self._capture(text="catatan yang akan dihapus")
        note_path = res.result["note_path"]
        self.assertTrue((self.vault / note_path).exists())

        undo = self.dispatcher.call(
            "undo_operation", {"operation_id": res.operation_id}
        )
        self.assertTrue(undo.ok, undo.error)
        self.assertFalse((self.vault / note_path).exists())

        op = self.conn.execute(
            "SELECT status FROM operations WHERE id = ?", (res.operation_id,)
        ).fetchone()
        self.assertEqual(op["status"], "undone")
        note = self.conn.execute(
            "SELECT id FROM notes WHERE path = ?", (note_path,)
        ).fetchone()
        self.assertIsNone(note)

    def test_undo_refuses_when_note_modified(self):
        res = self._capture(text="jangan diutak-atik")
        note_path = res.result["note_path"]
        (self.vault / note_path).write_text("diedit manual", encoding="utf-8")

        undo = self.dispatcher.call(
            "undo_operation", {"operation_id": res.operation_id}
        )
        self.assertFalse(undo.ok)
        self.assertEqual(undo.error["code"], "UNDO_FAILED")
        self.assertTrue((self.vault / note_path).exists())

    def test_double_undo_rejected(self):
        res = self._capture(text="undo sekali saja")
        self.dispatcher.call("undo_operation", {"operation_id": res.operation_id})
        again = self.dispatcher.call(
            "undo_operation", {"operation_id": res.operation_id}
        )
        self.assertFalse(again.ok)
        self.assertEqual(again.error["code"], "UNDO_FAILED")

    def test_empty_text_rejected(self):
        res = self._capture(text="   ")
        self.assertFalse(res.ok)
        self.assertEqual(res.error["code"], "CAPTURE_FAILED")

    def test_capture_without_config_is_rejected(self):
        dispatcher = LocalToolDispatcher(self.conn)  # no config
        res = dispatcher.call("capture_note", {"text": "x"})
        self.assertFalse(res.ok)
        self.assertEqual(res.error["code"], "CAPTURE_FAILED")


if __name__ == "__main__":
    unittest.main()
