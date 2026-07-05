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
from second_brain.vault import search


class OrganizeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sb-organize-"))
        self.vault = self.tmp / "vault"
        shutil.copytree(ROOT / "tests" / "fixtures" / "vault", self.vault)
        self.db_path = self.tmp / "organize.db"
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

    def _capture(self, **payload):
        return self.dispatcher.call("capture_note", payload, user_id="t:1")

    # --- search -----------------------------------------------------------

    def test_search_finds_note(self):
        self._capture(text="Vibe coding adalah arah baru membangun software")
        search.rebuild_index(self.conn, self.vault)
        res = self.dispatcher.call("search_vault", {"query": "vibe coding"})
        self.assertTrue(res.ok, res.error)
        paths = [r["path"] for r in res.result["results"]]
        self.assertTrue(any("Vibe coding" in p or p.endswith(".md") for p in paths))
        self.assertGreaterEqual(res.result["count"], 1)

    def test_search_excludes_sensitive_body(self):
        self._capture(text="catatan dengan kata bodyzzz999", title="Judul Aman",
                      sensitive=True)
        search.rebuild_index(self.conn, self.vault)

        body_hit = self.dispatcher.call("search_vault", {"query": "bodyzzz999"})
        self.assertEqual(body_hit.result["count"], 0)  # body not indexed

        title_hit = self.dispatcher.call("search_vault", {"query": "Judul Aman"})
        self.assertGreaterEqual(title_hit.result["count"], 1)  # title is indexed

    # --- get_note ---------------------------------------------------------

    def test_get_note_returns_content(self):
        cap = self._capture(text="isi catatan untuk dibaca")
        res = self.dispatcher.call("get_note", {"path": cap.result["note_path"]})
        self.assertTrue(res.ok, res.error)
        self.assertFalse(res.result["sensitive"])
        self.assertIn("isi catatan untuk dibaca", res.result["content"])
        self.assertIn("content_hash", res.result)

    def test_get_note_refuses_sensitive(self):
        res = self.dispatcher.call(
            "get_note", {"path": "00 Inbox/private-example.md"}
        )
        self.assertTrue(res.ok)
        self.assertTrue(res.result["sensitive"])
        self.assertNotIn("content", res.result)

    def test_get_note_path_traversal_rejected(self):
        res = self.dispatcher.call("get_note", {"path": "../../etc/passwd"})
        self.assertFalse(res.ok)
        self.assertEqual(res.error["code"], "READ_FAILED")

    # --- move -------------------------------------------------------------

    def test_move_note(self):
        cap = self._capture(text="catatan untuk dipindah ke project")
        src = cap.result["note_path"]
        res = self.dispatcher.call(
            "move_note", {"path": src, "to_folder": "10 Projects/Test Project"}
        )
        self.assertTrue(res.ok, res.error)
        self.assertTrue(res.result["to"].startswith("10 Projects/Test Project/"))
        self.assertFalse((self.vault / src).exists())
        self.assertTrue((self.vault / res.result["to"]).exists())

        note = self.conn.execute(
            "SELECT path, code_stage FROM notes WHERE path = ?", (res.result["to"],)
        ).fetchone()
        self.assertEqual(note["code_stage"], "organize")

    def test_move_conflict_guard(self):
        cap = self._capture(text="jangan dipindah kalau berubah")
        src = cap.result["note_path"]
        (self.vault / src).write_text("diedit di obsidian", encoding="utf-8")
        res = self.dispatcher.call(
            "move_note",
            {"path": src, "to_folder": "10 Projects/X", "expected_hash": "deadbeef"},
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.error["code"], "ORGANIZE_FAILED")
        self.assertTrue((self.vault / src).exists())

    def test_undo_move(self):
        cap = self._capture(text="pindah lalu undo")
        src = cap.result["note_path"]
        mv = self.dispatcher.call(
            "move_note", {"path": src, "to_folder": "20 Areas/Test"}
        )
        undo = self.dispatcher.call(
            "undo_operation", {"operation_id": mv.operation_id}
        )
        self.assertTrue(undo.ok, undo.error)
        self.assertTrue((self.vault / src).exists())
        self.assertFalse((self.vault / mv.result["to"]).exists())

    # --- update -----------------------------------------------------------

    def test_update_note_append(self):
        cap = self._capture(text="baris awal")
        path = cap.result["note_path"]
        res = self.dispatcher.call(
            "update_note", {"path": path, "text": "baris tambahan dari hermes"}
        )
        self.assertTrue(res.ok, res.error)
        content = (self.vault / path).read_text(encoding="utf-8")
        self.assertIn("baris awal", content)
        self.assertIn("baris tambahan dari hermes", content)

    def test_update_conflict_guard(self):
        cap = self._capture(text="konten asli")
        path = cap.result["note_path"]
        res = self.dispatcher.call(
            "update_note",
            {"path": path, "text": "tambah", "expected_hash": "wronghash"},
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.error["code"], "ORGANIZE_FAILED")

    def test_undo_update(self):
        cap = self._capture(text="konten untuk diubah lalu undo")
        path = cap.result["note_path"]
        original = (self.vault / path).read_text(encoding="utf-8")
        upd = self.dispatcher.call(
            "update_note", {"path": path, "text": "tambahan yang akan dibatalkan"}
        )
        undo = self.dispatcher.call(
            "undo_operation", {"operation_id": upd.operation_id}
        )
        self.assertTrue(undo.ok, undo.error)
        self.assertEqual((self.vault / path).read_text(encoding="utf-8"), original)

    def test_empty_update_rejected(self):
        cap = self._capture(text="ada isi")
        res = self.dispatcher.call(
            "update_note", {"path": cap.result["note_path"], "text": "   "}
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.error["code"], "ORGANIZE_FAILED")


if __name__ == "__main__":
    unittest.main()
