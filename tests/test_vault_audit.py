from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from second_brain.audit.vault_audit import audit_vault


class VaultAuditTests(unittest.TestCase):
    def test_audit_reads_fake_vault_without_writing(self):
        vault = ROOT / "tests" / "fixtures" / "vault"
        before = {path.relative_to(vault) for path in vault.rglob("*")}

        report = audit_vault(vault)

        after = {path.relative_to(vault) for path in vault.rglob("*")}
        self.assertEqual(before, after)
        self.assertGreaterEqual(report.markdown_files, 5)
        tags = dict(report.tags)
        self.assertGreaterEqual(tags["learning"], 2)
        self.assertTrue(any("00 Inbox" in folder for folder in report.para_like_folders))


if __name__ == "__main__":
    unittest.main()
