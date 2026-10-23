def build_prompt(java_class: object, project_context: str = "") -> str:
    return f"""Generate JUnit 5 MockMvc tests for the supplied Spring controller.
Return only compilable Java. Use only APIs present in the supplied source and
project inventory. Never invent classes, methods, DTOs, imports, or package names.
    For Java records, use the exact canonical constructor shown in the inventory;
    records do not have a no-argument constructor unless the source explicitly
    defines one. Do not write `new SomeRecord()` for a record with components.
    Use realistic values for every required record component.

PROJECT INVENTORY:
{project_context}

TARGET SOURCE:
{java_class.source}"""
