import json
import re
import unittest
from importlib import resources
from pathlib import Path

from threadlens.cli import main


class BundledSkillTests(unittest.TestCase):
    def test_skill_frontmatter_is_valid(self):
        skill_md = Path("threadlens/skills/threadlens/SKILL.md")
        content = skill_md.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\n"))

        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        self.assertIsNotNone(match)
        frontmatter = parse_simple_frontmatter(match.group(1))

        self.assertEqual(frontmatter["name"], "threadlens")
        self.assertIsInstance(frontmatter["description"], str)
        self.assertLessEqual(len(frontmatter["description"]), 1024)
        self.assertNotIn("<", frontmatter["description"])
        self.assertNotIn(">", frontmatter["description"])

    def test_skill_is_available_as_package_data(self):
        skill_md = resources.files("threadlens").joinpath("skills", "threadlens", "SKILL.md")
        metadata = resources.files("threadlens").joinpath("skills", "threadlens", "agents", "openai.yaml")

        self.assertTrue(skill_md.is_file())
        self.assertTrue(metadata.is_file())
        self.assertIn("threadlens search", skill_md.read_text(encoding="utf-8"))

    def test_skill_command_outputs_json_path(self):
        import io
        from contextlib import redirect_stdout

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main(["skill", "--json"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["name"], "threadlens")
        self.assertTrue(payload["skill_md"].endswith("SKILL.md"))


def parse_simple_frontmatter(value: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in value.splitlines():
        key, _, raw = line.partition(":")
        if key and raw:
            fields[key.strip()] = raw.strip()
    return fields
