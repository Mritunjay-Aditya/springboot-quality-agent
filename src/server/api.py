from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.generators.test_generator import TestGenerator
from src.llm.groq_client import GroqClient
from src.orchestrator.orchestrator import QualityOrchestrator

app = FastAPI(title="Spring Boot Quality Agent")


class ProjectRequest(BaseModel):
    project_path: str = Field(..., description="Absolute or working-directory-relative Spring Boot project path")


def _orchestrator(project_path: str, requires_llm: bool = True) -> QualityOrchestrator:
    path = Path(project_path).resolve()
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Project directory not found: {path}")
    config_path = Path(__file__).parents[2] / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    try:
        generator = TestGenerator(GroqClient(config.get("groq_model", "openai/gpt-oss-120b"))) if requires_llm else None
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return QualityOrchestrator(path, config, generator)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate-tests")
def generate_tests(request: ProjectRequest) -> dict[str, Any]:
    orchestrator = _orchestrator(request.project_path)
    paths = orchestrator.generate_tests()
    return {"tests_generated": paths, "generation_errors": orchestrator.generation_errors}


@app.post("/analyze")
def analyze(request: ProjectRequest) -> dict[str, Any]:
    return _orchestrator(request.project_path).run()


@app.post("/run-quality-gate")
def quality_gate(request: ProjectRequest) -> dict[str, Any]:
    return _orchestrator(request.project_path).run()
