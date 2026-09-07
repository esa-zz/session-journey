import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "journey.py"
SESSION_ID = "7ba3b25d-1055-49ef-91b6-4ed8cb73a20b"


class JourneyMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def start(self, *args):
        result = self.run_cli(
            "start",
            "--project-root",
            str(self.project_root),
            "--session-id",
            SESSION_ID,
            *args,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        journey = next(
            line.removeprefix("journey ")
            for line in result.stdout.splitlines()
            if line.startswith("journey ")
        )
        return self.project_root / journey

    def test_tool_defaults_agent_and_add_accepts_metadata_header(self):
        journey = self.start("--tool", "codex")
        content = journey.read_text(encoding="utf-8")
        self.assertIn("Tool: `codex`\nAgent: `default`\n", content)

        result = self.run_cli("add", str(journey), "--kind", "discovery", "--text", "Durable fact.")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(result.stdout.strip(), journey.read_text(encoding="utf-8"))

    def test_custom_agent_is_recorded(self):
        journey = self.start("--tool", "claude-code", "--agent-name", "reviewer")
        content = journey.read_text(encoding="utf-8")
        self.assertIn("Tool: `claude-code`\nAgent: `reviewer`\n", content)

    def test_legacy_header_still_accepts_events(self):
        journey = self.start()
        result = self.run_cli("add", str(journey), "--kind", "discovery", "--text", "Legacy file remains valid.")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_agent_requires_tool_and_slugs_are_lowercase(self):
        result = self.run_cli(
            "start",
            "--project-root",
            str(self.project_root),
            "--agent-name",
            "reviewer",
        )
        self.assertEqual(result.returncode, 2)

        result = self.run_cli(
            "start",
            "--project-root",
            str(self.project_root),
            "--tool",
            "Codex",
        )
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
