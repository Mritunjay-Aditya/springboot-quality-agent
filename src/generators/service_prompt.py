def build_prompt(java_class: object, project_context: str = "") -> str:
    return f"""Generate JUnit 5 Mockito tests for the supplied Java service.
Return only compilable Java.
Use only classes, methods, constructors, fields, and packages shown in the source
and project inventory. Do not invent types or methods. Do not call private
methods. Use the exact package declarations and imports from the source. If a
dependency is not listed, do not reference it.
Spring Data repositories have overloaded methods. Always use typed Mockito
matchers for overloaded calls: use `any(Sort.class)` for `findAll(Sort)`, never
plain `any()`. For verification, use an explicit `Sort` variable or
`ArgumentMatchers.<Sort>argThat(...)`, never an untyped `argThat(...)` for
`findAll`; use the exact argument type for other overloaded methods.

PROJECT INVENTORY:
{project_context}

TARGET SOURCE:
{java_class.source}"""
