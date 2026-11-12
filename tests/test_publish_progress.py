"""Exercise publication against temporary local repositories, without network."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools/scripts/publish_progress.py"
SPEC = importlib.util.spec_from_file_location("publish_progress", SCRIPT)
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


class PublishProgressTests(unittest.TestCase):
    def git(self, root, *args):
        return subprocess.run(["git", *args], cwd=root, text=True,
                              capture_output=True, check=True).stdout.strip()

    def configure(self, root):
        self.git(root, "config", "user.name", "MatyMeatBoy")
        self.git(root, "config", "user.email", "108221324+MatyMeatBoy@users.noreply.github.com")
        self.git(root, "config", "commit.gpgsign", "false")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ss1-publish-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.remote = self.base / "remote.git"
        self.work = self.base / "work"
        self.git(self.base, "init", "--bare", str(self.remote))
        self.git(self.base, "init", "-b", "main", str(self.work))
        self.configure(self.work)
        (self.work / "docs/progress").mkdir(parents=True)
        (self.work / "docs/progress/report.txt").write_text("old\n")
        (self.work / "version.txt").write_text("v1\n")
        (self.work / "README.md").write_text("fixture\n")
        self.git(self.work, "add", ".")
        self.git(self.work, "commit", "-m", "fixture initial")
        self.git(self.work, "remote", "add", "origin", str(self.remote))
        self.git(self.work, "push", "origin", "main")
        self.initial = self.tip()

    def tip(self):
        return self.git(self.remote, "rev-parse", "refs/heads/main")

    def generator(self, code):
        # The generator lives outside the checkout so its own file is never
        # an untracked input that would invalidate the clean-checkout test.
        script = self.base / "generate.py"
        script.write_text("from pathlib import Path\n" + code)
        return [sys.executable, str(script)]

    def test_fresh_main_publication(self):
        generate = self.generator("Path('docs/progress/report.txt').write_text('new\\n')\n")
        publisher.publish(self.work, generate=generate)
        self.assertNotEqual(self.tip(), self.initial)
        self.assertEqual(self.git(self.remote, "show", "main:docs/progress/report.txt"), "new")
        self.assertEqual(self.git(self.remote, "rev-parse", "main^"), self.initial)
        self.assertEqual(self.git(self.work, "status", "--porcelain"), "")

    def test_no_op_does_not_create_commit(self):
        publisher.publish(self.work, generate=self.generator("pass\n"))
        self.assertEqual(self.tip(), self.initial)
        self.assertEqual(self.git(self.work, "status", "--porcelain"), "")

    def test_reject_tracked_change_outside_progress(self):
        generate = self.generator("Path('README.md').write_text('changed\\n')\n")
        with self.assertRaisesRegex(RuntimeError, "outside docs/progress"):
            publisher.publish(self.work, generate=generate)
        self.assertEqual(self.tip(), self.initial)

    def test_reject_untracked_change_outside_progress(self):
        generate = self.generator("Path('unexpected.txt').write_text('new\\n')\n")
        with self.assertRaisesRegex(RuntimeError, "outside docs/progress"):
            publisher.publish(self.work, generate=generate)
        self.assertEqual(self.tip(), self.initial)

    def test_initial_dirty_checkout_is_refused_before_generation(self):
        marker = self.base / "generator-ran"
        generate = self.generator(f"Path({str(marker)!r}).touch()\n")
        (self.work / "README.md").write_text("dirty\n")
        with self.assertRaisesRegex(RuntimeError, "clean checkout"):
            publisher.publish(self.work, generate=generate)
        self.assertFalse(marker.exists())
        self.assertEqual(self.tip(), self.initial)

    def test_push_rejection_without_remote_advance_is_fatal(self):
        hook = self.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\necho 'fixture rejection' >&2\nexit 1\n")
        hook.chmod(0o755)
        generate = self.generator("Path('docs/progress/report.txt').write_text('new\\n')\n")
        with self.assertRaisesRegex(RuntimeError, "Progress push failed"):
            publisher.publish(self.work, attempts=3, generate=generate)
        self.assertEqual(self.tip(), self.initial)
        self.assertEqual(self.git(self.work, "rev-list", "--count", "HEAD"), "2")

    def test_remote_advance_retries_from_new_tip(self):
        rival = self.base / "rival"
        self.git(self.base, "clone", "--branch", "main", str(self.remote), str(rival))
        self.configure(rival)
        marker = self.base / "raced"
        generate = self.generator(
            "import subprocess\n"
            f"rival = Path({str(rival)!r})\n"
            f"marker = Path({str(marker)!r})\n"
            "if not marker.exists():\n"
            "    marker.touch()\n"
            "    (rival / 'version.txt').write_text('v2\\n')\n"
            "    for args in [('add', 'version.txt'), ('commit', '-m', 'concurrent fixture update'), ('push', 'origin', 'main')]:\n"
            "        subprocess.run(['git', *args], cwd=rival, check=True, capture_output=True)\n"
            "Path('docs/progress/report.txt').write_text(Path('version.txt').read_text())\n")
        publisher.publish(self.work, attempts=2, generate=generate)
        rival_tip = self.git(rival, "rev-parse", "HEAD")
        self.assertEqual(self.git(self.remote, "rev-parse", "main^"), rival_tip)
        self.assertEqual(self.git(self.remote, "show", "main:docs/progress/report.txt"), "v2")
        self.assertEqual(self.git(self.remote, "rev-list", "--count", "main"), "3")


if __name__ == "__main__":
    unittest.main()
