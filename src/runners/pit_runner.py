from pathlib import Path

from src.runners.maven_runner import CommandResult, run_maven


def run(project_path: Path, timeout: int = 900) -> CommandResult:
    return run_maven(project_path, ["pitest:mutationCoverage"], timeout)
