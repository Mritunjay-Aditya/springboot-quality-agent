import subprocess
import shutil
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).parents[2] / ".env")


@dataclass
class CommandResult:
    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


def _java21_home() -> str | None:
    candidates = []
    if os.getenv("JAVA_HOME") and "21" in os.environ["JAVA_HOME"]:
        candidates.append(os.environ["JAVA_HOME"])
    candidates.extend(str(path) for root in (
        Path(os.environ.get("ProgramFiles", "")) / "Eclipse Adoptium",
        Path(os.environ.get("ProgramFiles", "")) / "Java",
    ) if root.is_dir() for path in root.glob("*21*"))
    return next((path for path in candidates if Path(path, "bin", "java.exe").is_file()), None)


def run_maven(project_path: Path, goals: list[str], timeout: int = 900) -> CommandResult:
    executable = shutil.which("mvn.cmd") or shutil.which("mvn")
    command = [executable or ("mvn.cmd" if os.name == "nt" else "mvn"), *goals]
    environment = os.environ.copy()
    java_home = _java21_home()
    if java_home:
        environment["JAVA_HOME"] = java_home
        environment["PATH"] = os.path.join(java_home, "bin") + os.pathsep + environment["PATH"]
    try:
        completed = subprocess.run(
            command, cwd=project_path, capture_output=True, text=True,
            timeout=timeout, check=False, env=environment,
        )
        return CommandResult(command, completed.returncode, completed.stdout, completed.stderr)
    except subprocess.TimeoutExpired as exc:
        return CommandResult(command, -1, exc.stdout or "", exc.stderr or "", True)
    except OSError as exc:
        return CommandResult(command, -1, "", str(exc))
