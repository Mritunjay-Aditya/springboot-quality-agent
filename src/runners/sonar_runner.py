from pathlib import Path
import os

from src.runners.maven_runner import CommandResult, run_maven


def run(project_path: Path, timeout: int = 900) -> CommandResult:
    goals = ["sonar:sonar"]
    host_url = os.getenv("SONAR_HOST_URL")
    if host_url:
        goals.append(f"-Dsonar.host.url={host_url}")
    return run_maven(project_path, goals, timeout)
