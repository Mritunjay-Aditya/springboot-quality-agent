from src.parsers.java_ast_parser import JavaClass


def mock_fields(java_class: JavaClass) -> str:
    lines = []
    for field in java_class.fields:
        if field["name"] and "static" not in field["modifiers"]:
            lines.append(f"    @Mock\n    private {field['type']} {field['name']};")
    return "\n".join(lines)


def constructor_target(java_class: JavaClass) -> str:
    return f"    @InjectMocks\n    private {java_class.name} target;"
