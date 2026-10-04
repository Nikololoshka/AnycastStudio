from pathlib import Path
from unittest import TestCase

from platforms.tests.core.test_architecture import SourceModule

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.name
PURE_PARTS = ("core", "usecases")
FORBIDDEN_ROOTS = ("django", "celery", "asgiref", "accounts", "common", "config", "media", "publishing", "social")


def pure_modules() -> list[SourceModule]:
    return [
        SourceModule(path, PACKAGE)
        for part in PURE_PARTS
        for path in sorted((PACKAGE / part).rglob("*.py"))
        if "tests" not in path.parts
    ]


class ArchitectureScenarios(TestCase):
    def test_the_core_and_the_use_cases_do_not_depend_on_django_or_the_apps(self):
        for module in pure_modules():
            for name in module.imports():
                with self.subTest(module=module.name, imports=name):
                    self.assertNotIn(name.split(".")[0], FORBIDDEN_ROOTS)

    def test_the_core_does_not_know_the_use_cases(self):
        for module in pure_modules():
            if not module.name.startswith(f"{ROOT}.core"):
                continue
            for name in module.imports():
                with self.subTest(module=module.name, imports=name):
                    self.assertFalse(name.startswith(f"{ROOT}.usecases"))

    def test_the_core_and_the_use_cases_do_not_reach_the_wiring(self):
        for module in pure_modules():
            for name in module.imports():
                with self.subTest(module=module.name, imports=name):
                    self.assertNotIn(name, (f"{ROOT}.wiring", f"{ROOT}.queue", f"{ROOT}.tasks"))

    def test_behaviour_lives_in_classes(self):
        for module in pure_modules():
            with self.subTest(module=module.name):
                self.assertEqual(module.public_functions(), [])
