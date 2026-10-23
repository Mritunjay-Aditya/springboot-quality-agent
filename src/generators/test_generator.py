import re
from pathlib import Path

from src.generators.controller_prompt import build_prompt as controller_prompt
from src.generators.repository_prompt import build_prompt as repository_prompt
from src.generators.service_prompt import build_prompt as service_prompt
from src.generators.mock_generator import constructor_target, mock_fields
from src.llm.groq_client import GroqClient
from src.parsers.component_detector import ComponentType
from src.parsers.java_ast_parser import JavaClass


def _strip_markdown(content: str) -> str:
    match = re.search(r"```(?:java)?\s*(.*?)```", content, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(1)
    else:
        lines = content.splitlines()
        if lines and lines[0].strip().lower() in {"```", "```java"}:
            lines = lines[1:]
        content = "\n".join(line for line in lines if line.strip() != "```")
    return content.strip() + "\n"


def _validate_java_test(content: str, class_name: str) -> None:
    if "```" in content:
        raise ValueError(f"Groq returned Markdown fences for {class_name}")
    if f"class {class_name}Test" not in content and f"class {class_name}IT" not in content:
        raise ValueError(f"Generated test class for {class_name} is missing or has an unexpected name")
    if content.count("{") != content.count("}"):
        raise ValueError(f"Generated test for {class_name} has unbalanced braces")


def _validate_record_constructors(content: str, project_context: str) -> None:
    for match in re.finditer(
        r"-\s+[\w.]+\.(?P<name>[A-Za-z_$][\w$]*):\s+kind=record;.*?"
        r"constructor=\((?P<components>[^)]*)\)",
        project_context,
    ):
        if match.group("components").strip() and re.search(
            rf"\bnew\s+{re.escape(match.group('name'))}\s*\(\s*\)",
            content,
        ):
            raise ValueError(
                f"Generated test calls record {match.group('name')} with no arguments; "
                "use its canonical constructor"
            )


def _validate_overloaded_repository_matchers(content: str) -> None:
    if re.search(r"\.findAll\s*\(\s*any\s*\(\s*\)\s*\)", content):
        raise ValueError(
            "Generated test uses untyped any() for overloaded repository findAll; "
            "use any(Sort.class) or another exact argument type"
        )
    if re.search(r"\.findAll\s*\(\s*argThat\s*\(", content):
        raise ValueError(
            "Generated test uses untyped argThat for overloaded repository findAll; "
            "use an explicit Sort variable or ArgumentMatchers.<Sort>argThat(...)"
        )


class TestGenerator:
    def __init__(self, client: GroqClient, project_context: str = "", max_attempts: int = 2) -> None:
        self.client = client
        self.project_context = project_context
        self.max_attempts = max_attempts

    def _generate_valid(self, prompt: str, class_name: str) -> str:
        last_error: ValueError | None = None
        for attempt in range(self.max_attempts):
            retry = (
                "\nThis is a retry. Return a complete Java file with no Markdown "
                "fences, no ellipses, balanced braces, and the exact public test "
                "class name " + class_name + "Test.\n"
                if attempt
                else ""
            )
            content = _strip_markdown(self.client.generate(prompt + retry))
            try:
                _validate_java_test(content, class_name)
                _validate_record_constructors(content, self.project_context)
                _validate_overloaded_repository_matchers(content)
                return content
            except ValueError as exc:
                last_error = exc
        raise last_error or ValueError(f"Unable to generate a valid test for {class_name}")

    def generate(self, java_class: JavaClass, component: ComponentType) -> str:
        prompt_builder = {
            ComponentType.SERVICE: service_prompt,
            ComponentType.CONTROLLER: controller_prompt,
            ComponentType.REPOSITORY: repository_prompt,
        }.get(component, service_prompt)
        generated = self._generate_valid(
            prompt_builder(java_class, self.project_context), java_class.name
        )
        if "package " not in generated:
            generated = f"package {java_class.package};\n\n{generated}"
        if component == ComponentType.SERVICE:
            generated = self._ensure_mockito_structure(generated, java_class)
        _validate_java_test(generated, java_class.name)
        return generated

    @staticmethod
    def _ensure_mockito_structure(content: str, java_class: JavaClass) -> str:
        imports = []
        if "import org.mockito.Mock;" not in content and "@Mock" not in content:
            imports.append("import org.mockito.Mock;")
        if "import org.mockito.InjectMocks;" not in content and "@InjectMocks" not in content:
            imports.append("import org.mockito.InjectMocks;")
        if imports:
            package_end = content.find("\n", content.find("package "))
            content = content[:package_end + 1] + "\n" + "\n".join(imports) + content[package_end + 1:]
        if "@InjectMocks" not in content:
            marker = content.find("{", content.find("class "))
            if marker >= 0:
                content = (
                    content[:marker + 1] + "\n\n" + constructor_target(java_class)
                    + ("\n" + mock_fields(java_class) if mock_fields(java_class) else "")
                    + content[marker + 1:]
                )
        return content

    def regenerate(self, java_class: JavaClass, component: ComponentType, uncovered_methods: list[str]) -> str:
        prompt_builder = {
            ComponentType.SERVICE: service_prompt,
            ComponentType.CONTROLLER: controller_prompt,
            ComponentType.REPOSITORY: repository_prompt,
        }.get(component, service_prompt)
        prompt = (
            "Regenerate the Java unit test and add focused tests for these uncovered methods: "
            + ", ".join(uncovered_methods) + ". Return only compilable Java.\n"
            + prompt_builder(java_class, self.project_context)
        )
        generated = self._generate_valid(prompt, java_class.name)
        if "package " not in generated:
            generated = f"package {java_class.package};\n\n{generated}"
        if component == ComponentType.SERVICE:
            generated = self._ensure_mockito_structure(generated, java_class)
        _validate_java_test(generated, java_class.name)
        return generated

    def write_test(self, project_path: Path, java_class: JavaClass, content: str, integration: bool = False) -> Path:
        package_path = Path(*java_class.package.split(".")) if java_class.package else Path()
        suffix = "IT" if integration else "Test"
        destination = project_path / "src" / "test" / "java" / package_path / f"{java_class.name}{suffix}.java"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if integration and "@SpringBootTest" not in content:
            content = content.replace(f"package {java_class.package};", f"package {java_class.package};\n\nimport org.springframework.boot.test.context.SpringBootTest;\n\n@SpringBootTest", 1)
        destination.write_text(content, encoding="utf-8")
        return destination
