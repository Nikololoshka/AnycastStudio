import ast
from pathlib import Path
from unittest import TestCase

PACKAGE = Path(__file__).resolve().parents[2]
ROOT = PACKAGE.name
PLATFORMS = ("youtube", "tiktok", "instagram", "x")
REQUIRED_PARTS = ("core", "auth", "publish", "{platform}_platform.py", "{platform}_capabilities.py", "{platform}_validator.py")
FORBIDDEN_ROOTS = ("django", "accounts", "common", "config", "media", "publishing", "social", "platforms")


class SourceModule:
    def __init__(self, path: Path):
        self.path = path
        self.name = ".".join((ROOT, *path.relative_to(PACKAGE).with_suffix("").parts)).removesuffix(".__init__")
        self.tree = ast.parse(path.read_text(encoding="utf-8"))

    @property
    def is_package(self) -> bool:
        return self.path.name == "__init__.py"

    def imports(self) -> set[str]:
        found: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = self._absolute(node)
                found.add(base)
                found.update(f"{base}.{alias.name}" for alias in node.names)
        return found

    def public_functions(self) -> list[str]:
        return [
            node.name
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith("_")
        ]

    def _absolute(self, node: ast.ImportFrom) -> str:
        if node.level == 0:
            return node.module or ""
        parts = self.name.split(".")
        anchor = parts if self.is_package else parts[:-1]
        anchor = anchor[: len(anchor) - (node.level - 1)]
        return ".".join([*anchor, node.module] if node.module else anchor)


def source_modules() -> list[SourceModule]:
    return [SourceModule(path) for path in sorted(PACKAGE.rglob("*.py")) if "tests" not in path.parts]


def platform_of(module_name: str) -> str | None:
    parts = module_name.split(".")
    return parts[1] if parts[0] == ROOT and len(parts) > 1 and parts[1] in PLATFORMS else None


class ArchitectureScenarios(TestCase):
    def test_the_package_does_not_depend_on_django_or_the_apps(self):
        for module in source_modules():
            for name in module.imports():
                with self.subTest(module=module.name, imports=name):
                    self.assertNotIn(name.split(".")[0], FORBIDDEN_ROOTS)

    def test_a_platform_does_not_import_another_platform(self):
        for module in source_modules():
            own = platform_of(module.name)
            if own is None:
                continue
            for name in module.imports():
                with self.subTest(module=module.name, imports=name):
                    self.assertIn(platform_of(name), (None, own))

    def test_the_core_does_not_know_the_platforms(self):
        for module in source_modules():
            if not module.name.startswith(f"{ROOT}.core"):
                continue
            for name in module.imports():
                with self.subTest(module=module.name, imports=name):
                    self.assertIsNone(platform_of(name))
                    self.assertFalse(name.startswith(f"{ROOT}.platform_catalog"))

    def test_every_platform_has_the_same_shape(self):
        for platform in PLATFORMS:
            for part in REQUIRED_PARTS:
                with self.subTest(platform=platform, part=part):
                    self.assertTrue((PACKAGE / platform / part.format(platform=platform)).exists())

    def test_behaviour_lives_in_classes(self):
        for module in source_modules():
            with self.subTest(module=module.name):
                self.assertEqual(module.public_functions(), [])
