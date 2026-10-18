from pathlib import Path
from typing import Any

from src.coverage.jacoco_parser import parse_report
from src.generators.test_generator import TestGenerator
from src.runners.jacoco_runner import run as run_verify
from src.runners.maven_runner import run_maven
from src.runners.pit_runner import run as run_pit
from src.runners.sonar_runner import run as run_sonar
from src.reports.report_generator import write_report
from src.scanners.springboot_scanner import scan_project
from src.utils.logger import get_logger

logger = get_logger(__name__)


class QualityOrchestrator:
    def __init__(self, project_path: Path, config: dict[str, Any], generator: TestGenerator | None = None) -> None:
        self.project_path = project_path.resolve()
        self.config = config
        self.generator = generator
        self.generation_errors: list[str] = []

    def _validate_build(self) -> list[str]:
        pom = self.project_path / "pom.xml"
        if not pom.is_file():
            return ["pom.xml not found"]
        content = pom.read_text(encoding="utf-8", errors="replace")
        required = {
            "JaCoCo": "jacoco",
            "PIT": "pitest",
            "Sonar Maven Plugin": "sonar",
        }
        return [label for label, marker in required.items() if marker not in content.lower()]

    def generate_tests(self) -> list[str]:
        if self.generator is None:
            raise RuntimeError("A Groq test generator is required")
        scanned = scan_project(self.project_path)
        inventory = "\n".join(
            f"- {java_class.package}.{java_class.name}: "
            f"annotations={java_class.annotations}; "
            f"imports={java_class.imports}; "
            f"methods={[method.name for method in java_class.methods]}; "
            f"fields={[field['type'] + ' ' + field['name'] for field in java_class.fields]}"
            for java_class, _ in scanned
        )
        self.generator.project_context = inventory
        generated = []
        for java_class, component in scanned:
            if component.value == "unknown":
                continue
            content = None
            try:
                content = self.generator.generate(java_class, component)
                generated.append(str(self.generator.write_test(self.project_path, java_class, content)))
            except ValueError as exc:
                logger.error("Skipping invalid generated test for %s: %s", java_class.name, exc)
                self.generation_errors.append(f"{java_class.name}: {exc}")
            if self.config.get("integration_tests", False):
                if content is not None:
                    generated.append(str(self.generator.write_test(
                        self.project_path, java_class, content, integration=True
                    )))
        return generated

    def run(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "tests_generated": [], "coverage": {}, "pit_results": {},
            "sonar_results": {}, "execution_results": {},
        }
        missing = self._validate_build()
        if missing:
            report["execution_results"]["missing_maven_plugins"] = missing
        if self.generator is not None:
            report["tests_generated"] = self.generate_tests()
        report["generation_errors"] = self.generation_errors
        timeout = int(self.config.get("command_timeout_seconds", 900))
        test_result = run_maven(self.project_path, ["clean", "test"], timeout)
        report["execution_results"]["mvn_clean_test"] = vars(test_result)
        if test_result.return_code == 0:
            verify_result = run_verify(self.project_path, timeout)
            report["execution_results"]["mvn_clean_verify"] = vars(verify_result)
            if verify_result.return_code != 0:
                report["pit_results"] = {"skipped": True, "reason": "Maven verify failed"}
                report["sonar_results"] = {"skipped": True, "reason": "Maven verify failed"}
                report["coverage"] = {
                    "available": False,
                    "error": "Maven verify failed; JaCoCo report is not trustworthy",
                }
                write_report(self.project_path, report)
                return report
        else:
            verify_result = None
            report["execution_results"]["mvn_clean_verify"] = {
                "skipped": True, "reason": "mvn clean test failed"
            }
            report["pit_results"] = {"skipped": True, "reason": "Maven tests failed"}
            report["sonar_results"] = {"skipped": True, "reason": "Maven tests failed"}
            report["coverage"] = {"available": False, "error": "Maven tests failed"}
            write_report(self.project_path, report)
            return report
        report["coverage"] = parse_report(self.project_path / "target" / "site" / "jacoco" / "jacoco.xml")
        threshold = float(self.config.get("coverage_threshold", 0.8))
        report["coverage"]["threshold"] = threshold
        report["coverage"]["below_threshold"] = (
            report["coverage"].get("counters", {}).get("instruction", {}).get("percentage", 1.0) < threshold
        )
        if (
            verify_result is not None
            and verify_result.return_code == 0
            and report["coverage"]["below_threshold"]
            and self.generator is not None
        ):
            uncovered_by_class: dict[str, list[str]] = {}
            for item in report["coverage"].get("uncovered_methods", []):
                uncovered_by_class.setdefault(item["class"], []).append(item["method"])
            regenerated = []
            for java_class, component in scan_project(self.project_path):
                if component.value == "unknown":
                    continue
                methods = uncovered_by_class.get(java_class.name, [])
                if methods:
                    try:
                        content = self.generator.regenerate(java_class, component, methods)
                        regenerated.append(str(self.generator.write_test(self.project_path, java_class, content)))
                    except ValueError as exc:
                        logger.error("Skipping invalid regenerated test for %s: %s", java_class.name, exc)
                        self.generation_errors.append(f"{java_class.name} regeneration: {exc}")
            report["execution_results"]["coverage_regeneration"] = regenerated
            if regenerated:
                regeneration_result = run_maven(self.project_path, ["test"], timeout)
                report["execution_results"]["post_regeneration_test"] = vars(regeneration_result)
                if regeneration_result.return_code != 0:
                    report["pit_results"] = {"skipped": True, "reason": "Regenerated tests failed"}
                    report["sonar_results"] = {"skipped": True, "reason": "Regenerated tests failed"}
                    write_report(self.project_path, report)
                    return report
        pit_result = run_pit(self.project_path, timeout)
        report["pit_results"] = vars(pit_result)
        sonar_result = run_sonar(self.project_path, timeout)
        report["sonar_results"] = vars(sonar_result)
        write_report(self.project_path, report)
        return report
