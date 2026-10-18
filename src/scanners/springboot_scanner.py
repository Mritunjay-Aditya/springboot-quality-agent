from pathlib import Path

from src.parsers.component_detector import ComponentType, detect_component
from src.parsers.java_ast_parser import JavaClass, parse_project


def scan_project(project_path: Path) -> list[tuple[JavaClass, ComponentType]]:
    source_root = project_path / "src" / "main" / "java"
    if not source_root.is_dir():
        raise FileNotFoundError(f"Spring source directory does not exist: {source_root}")
    return [(java_class, detect_component(java_class)) for java_class in parse_project(source_root)]
