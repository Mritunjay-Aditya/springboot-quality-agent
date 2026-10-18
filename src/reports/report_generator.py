import json
from pathlib import Path
from typing import Any


def write_report(project_path: Path, report: dict[str, Any]) -> Path:
    destination = project_path / "quality-report.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return destination
