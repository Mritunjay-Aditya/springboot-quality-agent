from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import javalang
import re


@dataclass
class JavaParameter:
    name: str
    type: str


@dataclass
class JavaMethod:
    name: str
    return_type: str
    parameters: list[JavaParameter] = field(default_factory=list)
    annotations: list[str] = field(default_factory=list)


@dataclass
class JavaClass:
    source_path: Path
    package: str
    name: str
    annotations: list[str]
    fields: list[dict[str, Any]]
    methods: list[JavaMethod]
    source: str = ""
    imports: list[str] = field(default_factory=list)
    kind: str = "class"


def _type_name(type_node: Any) -> str:
    if type_node is None:
        return "void"
    name = getattr(type_node, "name", str(type_node))
    arguments = getattr(type_node, "arguments", None) or []
    if arguments:
        name += "<" + ", ".join(_type_name(argument.type) for argument in arguments) + ">"
    dimensions = getattr(type_node, "dimensions", None) or []
    return name + "[]" * len(dimensions)


def _annotation_names(annotations: Any) -> list[str]:
    values = annotations.values() if hasattr(annotations, "values") else annotations
    return [annotation.name for annotation in values]


def parse_java_file(path: Path) -> JavaClass:
    source = path.read_text(encoding="utf-8")
    try:
        tree = javalang.parse.parse(source)
    except javalang.parser.JavaSyntaxError:
        record = re.search(
            r"\b(?:public\s+)?record\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)",
            source,
        )
        if record is None:
            raise
        package_match = re.search(r"\bpackage\s+([\w.]+)\s*;", source)
        imports = re.findall(r"\bimport\s+(?:static\s+)?([\w.$]+)\s*;", source)
        fields = []
        for component in record.group(2).split(","):
            component = component.strip()
            if not component:
                continue
            match = re.match(r"(.+?)\s+([A-Za-z_$][\w$]*)$", component)
            if match:
                fields.append({
                    "name": match.group(2),
                    "type": match.group(1).strip(),
                    "modifiers": [],
                })
        return JavaClass(
            source_path=path,
            package=package_match.group(1) if package_match else "",
            name=record.group(1),
            annotations=[],
            fields=fields,
            methods=[],
            source=source,
            imports=imports,
            kind="record",
        )
    package = tree.package.name if tree.package else ""
    declaration = next(
        (node for node in tree.types if isinstance(node, (javalang.tree.ClassDeclaration,
                                                          javalang.tree.InterfaceDeclaration))),
        None,
    )
    if declaration is None:
        raise ValueError(f"No class or interface declaration found in {path}")

    fields = []
    for field in declaration.fields:
        fields.append({
            "name": field.declarators[0].name if field.declarators else "",
            "type": _type_name(field.type),
            "modifiers": sorted(field.modifiers),
        })
    methods = []
    for method in declaration.methods:
        methods.append(JavaMethod(
            name=method.name,
            return_type=_type_name(method.return_type),
            parameters=[
                JavaParameter(parameter.name, _type_name(parameter.type))
                for parameter in method.parameters
            ],
            annotations=_annotation_names(method.annotations),
        ))
    return JavaClass(
        source_path=path,
        package=package,
        name=declaration.name,
        annotations=_annotation_names(declaration.annotations),
        fields=fields,
        methods=methods,
        source=source,
        imports=[import_node.path for import_node in tree.imports],
        kind="class",
    )


def parse_project(source_root: Path) -> list[JavaClass]:
    classes = []
    for path in sorted(source_root.rglob("*.java")):
        try:
            classes.append(parse_java_file(path))
        except (OSError, javalang.parser.JavaSyntaxError, ValueError):
            continue
    return classes
