def build_prompt(java_class: object, project_context: str = "") -> str:
    return f"""Generate JUnit 5 @DataJpaTest tests for the supplied Spring
repository. Return only compilable Java. Use only APIs present in the supplied
source and project inventory. Never invent classes, methods, DTOs, or package
names or imports.

PROJECT INVENTORY:
{project_context}

TARGET SOURCE:
{java_class.source}"""
