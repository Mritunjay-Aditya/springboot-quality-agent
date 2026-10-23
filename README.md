# Spring Boot Quality Agent

The Spring Boot Quality Agent is a Python-based AI quality pipeline for Java
Spring Boot projects. It scans Java source code, parses classes with
`javalang`, identifies Spring components, asks Groq to generate tests, writes
those tests into the target project, runs Maven quality tools, parses JaCoCo
coverage, optionally regenerates tests for uncovered methods, and writes a
machine-readable report.

This is an MVP. Generated tests are grounded in the target source and
validated before they are saved, but they should still be reviewed for
project-specific behavior.

## What the agent does

For a target Spring Boot project, the agent:

1. Scans `src/main/java`.
2. Parses Java packages, imports, classes, annotations, fields, methods,
   parameters, and return types.
3. Detects supported Spring stereotypes.
4. Builds a project inventory so prompts can refer to real project types.
5. Generates tests with the Groq model configured in `config.yaml`.
6. Removes Markdown wrappers and rejects malformed or incomplete Java output.
7. Writes tests under the matching package in `src/test/java`.
8. Runs `mvn clean test`.
9. Runs `mvn clean verify`.
10. Parses `target/site/jacoco/jacoco.xml`.
11. Regenerates tests for uncovered methods when coverage is below the
    configured threshold.
12. Re-runs tests after regeneration.
13. Runs PIT mutation testing.
14. Runs SonarQube analysis.
15. Writes `quality-report.json` in the target project.

The agent deliberately stops downstream quality stages when Maven tests or
verification fail. This prevents stale JaCoCo, PIT, or Sonar output from being
reported as a successful run.

## Architecture

```text
FastAPI
  -> QualityOrchestrator
       -> Spring scanner
            -> javalang AST parser
            -> Spring stereotype detector
       -> Groq test generator
            -> prompts and Mockito helpers
            -> src/test/java/<package>/<Class>Test.java
       -> Maven clean test / verify
       -> JaCoCo XML parser
       -> coverage-driven regeneration
       -> PIT mutation testing
       -> Sonar Maven analysis
       -> quality-report.json
```

### Repository structure

- `src/server/api.py`: FastAPI application and HTTP endpoints.
- `src/orchestrator/orchestrator.py`: end-to-end workflow, validation, and
  failure gating.
- `src/llm/groq_client.py`: Groq client and `.env` loading.
- `src/scanners/springboot_scanner.py`: discovers Java source files and
  returns parsed classes with detected component types.
- `src/parsers/java_ast_parser.py`: extracts Java source structure with
  `javalang`.
- `src/parsers/component_detector.py`: classifies Spring stereotypes.
- `src/generators/`: prompts, Mockito helpers, output validation, and file
  generation.
- `src/runners/`: Maven, JaCoCo, PIT, and Sonar command execution.
- `src/coverage/jacoco_parser.py`: JaCoCo XML counters and uncovered methods.
- `src/reports/report_generator.py`: writes the final JSON report.
- `config.yaml`: model, timeout, coverage, and feature settings.
- `.env.example`: template for local secrets.
- `.env`: local secret file; ignored by Git and never to be committed.

The analyzed Spring Boot project is separate from this repository. Generated
tests are written to that project's `src/test/java` directory, and its
`quality-report.json` is written at the project root.

## Spring component detection

The detector recognizes these annotations:

| Annotation | Test style |
|---|---|
| `@Service` | JUnit 5 and Mockito |
| `@Controller` | JUnit 5 and MockMvc |
| `@RestController` | JUnit 5 and MockMvc |
| `@Repository` | JUnit 5 and `@DataJpaTest` |
| Other or no stereotype | Skipped by test generation |

Both simple and fully qualified annotation names are supported. For example,
`@Service` and `@org.springframework.stereotype.Service` are treated
equivalently.

## Groq integration

The agent uses:

```python
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
```

The default model is `openai/gpt-oss-120b`. The API key is loaded from
`GROQ_API_KEY`; it is never hardcoded in the source.

The prompt includes the target class source, imports, fields, methods,
annotations, and a project inventory. The prompt explicitly instructs the
model not to invent classes, methods, packages, or imports. Returned output is
checked for a package declaration, the expected test class, balanced braces,
and removal of Markdown fences. Java records are parsed separately and their
canonical constructor components are included in the inventory. A
deterministic guard rejects generated calls that omit required record
components, then retries the generation. Invalid output is
retried within a bounded limit and then recorded in `generation_errors` instead
of being written.

For Spring Data repository overloads, generated Mockito matchers are required
to be typed. For example, a service calling `findAll(Sort)` must use
`any(Sort.class)` for stubbing and an explicit `Sort` variable or
`ArgumentMatchers.<Sort>argThat(...)` for verification. Untyped `any()` and
`argThat(...)` can make `findAll(Sort)` and `findAll(Example)` ambiguous to
`javac`.

## Prerequisites

Install:

- Python 3.10 or newer.
- Java 21 for the target Maven project.
- Maven 3.9 or newer.
- A Groq API key.
- A SonarQube server and credentials if Sonar is enabled.

Java 21 is recommended because older Mockito/Byte Buddy combinations can fail
under newer Java releases. On Windows, the Maven runner resolves `mvn.cmd`
and prefers a detected Java 21 installation for Maven subprocesses.

Verify the local tools:

```powershell
java -version
mvn -version
```

The target project must contain:

- `pom.xml`
- `src/main/java`
- JaCoCo Maven configuration
- PIT Maven configuration
- Sonar Maven plugin configuration

The agent reports missing plugin markers before running the pipeline. Plugin
validation is a warning; Maven itself remains the final authority.

## Installation

From PowerShell:

```powershell
cd F:\MCP\quality-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`:

```env
GROQ_API_KEY=your-groq-api-key
SONAR_HOST_URL=http://localhost:9000
SONAR_TOKEN=your-sonarqube-token
```

The application loads `.env` relative to the quality-agent project. Both Groq
and Sonar settings are available to the agent's Maven subprocesses. The file
is ignored by Git. Replace `your-sonarqube-token` with a token generated in
SonarQube. If using shell variables instead:

```powershell
$env:GROQ_API_KEY = "your-groq-api-key"
$env:SONAR_HOST_URL = "http://localhost:9000"
$env:SONAR_TOKEN = "your-sonarqube-token"
```

Set the variable before starting Uvicorn. Do not commit or paste real API keys
into source files, reports, terminals, or issue trackers. If a key has already
been exposed, revoke it and create a replacement.

## Starting the API

Start the server from the quality-agent directory:

```powershell
cd F:\MCP\quality-agent
.\.venv\Scripts\Activate.ps1
python -m uvicorn src.server.api:app --host 127.0.0.1 --port 8000
```

Keep this terminal running. The interactive Swagger UI is available at
<http://127.0.0.1:8000/docs>, and the OpenAPI document is available at
<http://127.0.0.1:8000/openapi.json>.

Check the server from another PowerShell terminal:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/health"
```

Expected response:

```json
{"status":"ok"}
```

## API usage

### Windows paths and JSON

A Windows backslash is an escape character in JSON. This is invalid:

```json
{"project_path":"C:\work\my-spring-app"}
```

Use PowerShell's JSON serializer to avoid escaping mistakes:

```powershell
$body = @{
  project_path = "C:\work\my-spring-app"
} | ConvertTo-Json
```

### Generate tests only

This endpoint scans the project and writes unit tests, but does not run the
full quality pipeline:

```powershell
$body = @{
  project_path = "C:\work\my-spring-app"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/generate-tests" `
  -ContentType "application/json" `
  -Body $body
```

The response contains:

- `tests_generated`: paths of files successfully written.
- `generation_errors`: classes whose output was rejected or could not be
  generated.

Review generated files and run `mvn clean test` in the target project before
using the complete pipeline.

### Run the complete analysis

```powershell
$body = @{
  project_path = "C:\work\my-spring-app"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/analyze" `
  -ContentType "application/json" `
  -Body $body
```

`/run-quality-gate` runs the same complete workflow:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/run-quality-gate" `
  -ContentType "application/json" `
  -Body $body
```

The analysis request is synchronous. It stays open while Maven, PIT, and
Sonar run, or until the configured timeout is reached.

## Maven and quality-tool behavior

### JaCoCo

The target Maven project must bind JaCoCo's `prepare-agent` and `report`
goals to its lifecycle. A typical report is:

```text
target/site/jacoco/jacoco.xml
target/site/jacoco/index.html
```

The agent parses instruction, branch, line, complexity, method, and class
counters. It also records uncovered methods and compares instruction coverage
with `coverage_threshold` from `config.yaml`.

To open the HTML report manually after a successful build:

```powershell
Start-Process "C:\work\my-spring-app\target\site\jacoco\index.html"
```

If the file does not exist, inspect the Maven result first. A failed
verification or missing JaCoCo lifecycle binding means there is no current
report to open.

## Viewing generated HTML reports

The reports are generated inside the analyzed Spring Boot project, not inside
the Python quality-agent folder. For a project at
`C:\work\my-spring-app`, the files are:

```text
C:\work\my-spring-app\target\site\jacoco\index.html
C:\work\my-spring-app\target\pit-reports\index.html
```

Open them in the default browser from PowerShell:

```powershell
Start-Process "C:\work\my-spring-app\target\site\jacoco\index.html"
Start-Process "C:\work\my-spring-app\target\pit-reports\index.html"
```

You can also paste these local file URLs into a browser:

```text
file:///C:/work/my-spring-app/target/site/jacoco/index.html
file:///C:/work/my-spring-app/target/pit-reports/index.html
```

Or open the files in VS Code:

```powershell
code "C:\work\my-spring-app\target\site\jacoco\index.html"
code "C:\work\my-spring-app\target\pit-reports\index.html"
```

### What the JaCoCo report shows

The JaCoCo report contains:

- Instruction coverage
- Line coverage
- Branch coverage
- Method coverage
- Class coverage
- Coverage by package, class, and method
- Uncovered source lines and methods

JaCoCo is generated by the Maven `verify` lifecycle:

```powershell
cd C:\work\my-spring-app
mvn clean verify
```

### What the PIT report shows

The PIT report contains:

- Number of mutations created
- Mutations killed by tests
- Surviving mutations
- Mutation coverage
- Test strength
- Results by package, class, and source line

PIT is generated with:

```powershell
cd C:\work\my-spring-app
mvn pitest:mutationCoverage
```

These HTML files are generated build output. They may be removed by
`mvn clean` and recreated by the commands above or by the agent's
`/analyze` or `/run-quality-gate` endpoint. They normally should not be
committed to source control.

### Coverage-driven regeneration

When instruction coverage is below the configured threshold, the orchestrator
groups uncovered methods by detected Spring component and asks Groq for a
targeted test regeneration. It writes the regenerated test and runs Maven
tests again. PIT and Sonar are skipped if those regenerated tests fail.

Coverage regeneration is intentionally restricted to recognized Spring
components. Plain model, configuration, and application bootstrap classes are
not automatically treated as test-generation targets.

### PIT

PIT runs:

```text
mvn pitest:mutationCoverage
```

JUnit 5 projects generally need the PIT JUnit 5 plugin dependency in the PIT
Maven plugin configuration. PIT output and its return code are preserved in
the report. PIT is skipped when Maven tests or verification fail.

### SonarQube

Sonar runs:

```text
mvn sonar:sonar
```

Configure Sonar before starting Uvicorn:

```powershell
$env:SONAR_HOST_URL = "http://localhost:9000"
$env:SONAR_TOKEN = "your-sonar-token"
```

The agent passes `SONAR_HOST_URL` to Maven and keeps `SONAR_TOKEN` in the
subprocess environment. The token is not added to the command or report.
Sonar output and its return code are preserved in the report. Restart Uvicorn
after changing these values.

## Report format

The final report is written to the target project, for example:

```text
C:\work\my-spring-app\quality-report.json
```

The top-level shape is:

```json
{
  "tests_generated": [],
  "generation_errors": [],
  "summary": {},
  "coverage": {},
  "pit_results": {},
  "sonar_results": {},
  "execution_results": {}
}
```

Important fields:

- `tests_generated`: files successfully written by the generator.
- `generation_errors`: rejected Groq output and generation failures.
- `coverage`: JaCoCo availability, counters, threshold, and uncovered methods.
- `pit_results`: PIT command, output, return code, or skip reason.
- `sonar_results`: Sonar command, output, return code, or skip reason.
- `execution_results`: Maven results, missing plugin warnings, and
  regeneration results.
- `summary`: an easy-to-read status, result for each stage, coverage
  percentage, and recommended next action.

Command results include the command, return code, standard output, standard
error, and timeout status. Coverage values are decimals: `0.80` means 80%.
Treat coverage, PIT, and Sonar as current only when their prerequisite Maven
stages have return code `0`.

## Troubleshooting

### `422 Unprocessable Entity` and `Invalid \escape`

The request body is not valid JSON because a Windows path contains unescaped
backslashes. Use `ConvertTo-Json`, as shown above. In raw JSON, use:

```json
{"project_path":"C:\\work\\my-spring-app"}
```

### `GROQ_API_KEY is required`

Create `.env` from `.env.example`, set the key, and restart Uvicorn. Existing
server processes do not automatically reload environment changes.

### SonarQube authentication fails

Set `SONAR_HOST_URL` and `SONAR_TOKEN` in the same PowerShell session used to
start Uvicorn, then restart the server. A successful run reports
`summary.stage_results.sonar` as `passed`.

### Maven cannot be found

Install Maven, add its `bin` directory to `PATH`, verify `mvn -version`, and
restart Uvicorn. On Windows, the agent invokes the resolved `mvn.cmd`.

### Maven or Mockito uses Java 25

Install Java 21 and make it available to the agent. Restart Uvicorn after
changing Java configuration. The runner also looks for a Java 21 installation
for Maven subprocesses.

### Generated Java does not compile

Use `/generate-tests` first, inspect the first compiler error, and correct or
remove the generated test before running `/analyze`. Generated tests must use
real packages, imports, constructors, methods, and valid data for the target
application. Do not change production visibility merely to satisfy invented
test code.

### Generated output contains Markdown or is truncated

Restart Uvicorn so the current generator code is loaded. The generator strips
Markdown fences and rejects unbalanced or incomplete output. The failure will
appear in `generation_errors`.

### JaCoCo HTML cannot be opened

Run `mvn clean verify` in the target project and confirm both
`target/jacoco.exec` and `target/site/jacoco/index.html` exist. If verification
fails, inspect the compiler/test error before trying to open the report.

### PIT or Sonar fails

Inspect the captured `stdout` and `stderr` in `quality-report.json`. Confirm
the relevant Maven plugin, Java version, network access, server URL, and
credentials. A skipped result caused by an earlier Maven failure is expected
and must be fixed at the earlier stage first.

## Safe operating procedure

1. Start the API and call `/health`.
2. Call `/generate-tests` before `/analyze` on a new project.
3. Review generated files.
4. Run `mvn clean test` in the target project.
5. Fix or remove project-specific tests that do not compile or pass.
6. Call `/analyze`.
7. Inspect `quality-report.json`.
8. Trust downstream results only when the relevant return codes are zero.

If an experiment must be undone, back up existing tests first and remove only
the generated files or the target project's test source directory. Never remove
the target project's production source.

## Configuration

`config.yaml` currently contains:

```yaml
coverage_threshold: 0.80
command_timeout_seconds: 900
java_version: "21"
groq_model: openai/gpt-oss-120b
test_source_root: src/test/java
integration_tests: false
quality_report: quality-report.json
```

- `coverage_threshold`: decimal instruction coverage target.
- `command_timeout_seconds`: timeout for each Maven subprocess.
- `java_version`: expected Maven runtime.
- `groq_model`: Groq model used for generation.
- `test_source_root`: target test source root.
- `integration_tests`: opt-in `<ClassName>IT.java` generation flag.
- `quality_report`: report filename in the target project.

## Security and privacy

Java source context is sent to the configured Groq model. Do not point the
agent at source containing secrets, private keys, production credentials, or
personal data unless that use is approved. Keep `.env`, Sonar tokens, Maven
settings, and generated reports out of source control. Rotate any credential
that has been exposed.

## Future roadmap

- Per-file compile feedback and targeted retry.
- Backups and non-destructive patching during coverage regeneration.
- Deterministic templates for common Spring patterns.
- Datasource-aware Testcontainers integration tests.
- Asynchronous job tracking for long-running analyses.
- Sonar API result retrieval and richer report parsing.
- HTML reports and CI artifact publishing.
