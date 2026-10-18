def build_prompt(java_class: object, project_context: str = "") -> str:
    return f"""Generate JUnit 5 MockMvc tests for the supplied Spring controller.
Return only compilable Java. Use only APIs present in the supplied source and
project inventory. Never invent classes, methods, DTOs, imports, or package names.

PROJECT INVENTORY:
{project_context}

TARGET SOURCE:
{java_class.source}"""
