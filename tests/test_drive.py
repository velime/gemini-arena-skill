"""Offline end-to-end tests for drive.py using tests/fake_agy.py instead of the real agy.

    python -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(os.path.dirname(HERE), "skills", "gemini-arena")
DRIVE = os.path.join(SKILL, "drive.py")
FAKE = os.path.join(HERE, "fake_agy.py")


class DriveTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.task = os.path.join(self.root, "task.md")
        with open(self.task, "w", encoding="utf-8") as fh:
            fh.write("Write a haiku about tests.")

    def tearDown(self):
        self._tmp.cleanup()

    def drive(self, *args, **env):
        e = dict(os.environ, AGY_WORK_ROOT=self.root, AGY_CMD=json.dumps([sys.executable, FAKE]), **env)
        return subprocess.run([sys.executable, DRIVE] + list(args), capture_output=True, text=True, env=e)

    def init(self, slug, agents=4):
        r = self.drive("init", "--slug", slug, "--agents", str(agents), "--seed", "1", "--task-file", self.task)
        self.assertEqual(r.returncode, 0, r.stderr)
        return os.path.join(self.root, "arena", slug)

    def winner(self, d):
        r = subprocess.run([sys.executable, os.path.join(SKILL, "bracket.py"), "winner", "--dir", d],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_full_run_gemini_judges_everything(self):
        d = self.init("full")
        r = self.drive("run", "--slug", "full", "--claude-judge-alive", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CHAMPION", self.winner(d))

    def test_claude_judges_last_rounds_then_resumes(self):
        d = self.init("claude")
        r = self.drive("run", "--slug", "claude")  # 4 agents: round 1 starts with 4 alive, so Claude judges
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("CLAUDE JUDGES NEEDED", r.stdout)
        for line in r.stdout.splitlines():  # act as the Claude judge: run the brief through the fake
            if line.startswith("  ") and ".judge" in line:
                brief = line.split()[-1]
                subprocess.run([sys.executable, FAKE, "-p", "Read %s and follow it exactly. x" % brief], check=True,
                               capture_output=True)
        for _ in range(4):  # judge rounds come in turn: round 1, round 2 (and final if any)
            r = self.drive("run", "--slug", "claude")
            if r.returncode != 3:
                break
            for line in r.stdout.splitlines():
                if line.startswith("  ") and ".judge" in line:
                    subprocess.run([sys.executable, FAKE, "-p", "Read %s and follow it exactly. x" % line.split()[-1]],
                                   check=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CHAMPION", self.winner(d))

    def test_quota_stops_and_resumes(self):
        d = self.init("quota")
        r = self.drive("run", "--slug", "quota", "--claude-judge-alive", "0", FAKE_QUOTA_AFTER="5")
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("QUOTA", r.stdout)
        self.assertTrue(os.path.isfile(os.path.join(d, "arena.json")), "state survives")
        r = self.drive("run", "--slug", "quota", "--claude-judge-alive", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CHAMPION", self.winner(d))

    def test_slug_cannot_escape_the_work_root(self):
        r = self.drive("init", "--slug", "..\\evil", "--task-file", self.task)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
