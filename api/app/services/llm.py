import json
from pathlib import Path
from typing import Any, Protocol, TypeVar

import httpx
import yaml
from pydantic import BaseModel

from api.app.core.config import Settings, get_settings

SchemaT = TypeVar("SchemaT", bound=BaseModel)
REPO_ROOT = Path(__file__).resolve().parents[3]


class LLMError(RuntimeError):
    """Raised when an LLM request or fixture cannot be completed safely."""


class LLMClient(Protocol):
    async def complete(
        self,
        prompt_key: str,
        version: str,
        variables: dict[str, Any],
        schema: type[SchemaT],
    ) -> SchemaT: ...


def _prompt_path(prompt_key: str) -> Path:
    return REPO_ROOT / "prompts" / f"{prompt_key}.yaml"


def load_prompt(prompt_key: str, version: str, variables: dict[str, Any]) -> dict[str, Any]:
    path = _prompt_path(prompt_key)
    if not path.is_file():
        raise LLMError(f"Unknown prompt: {prompt_key}@{version}")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("version") != version:
        raise LLMError(f"Unknown prompt version: {prompt_key}@{version}")
    try:
        return {
            **document,
            "system": str(document["system"]).format(**variables),
            "user": str(document["user"]).format(**variables),
        }
    except KeyError as exc:
        raise LLMError(f"Missing prompt variable: {exc.args[0]}") from exc


class FakeLLM:
    def __init__(self, fixture_case: str = "default") -> None:
        self.fixture_case = fixture_case

    async def complete(
        self,
        prompt_key: str,
        version: str,
        variables: dict[str, Any],
        schema: type[SchemaT],
    ) -> SchemaT:
        load_prompt(prompt_key, version, variables)
        fixture = (
            REPO_ROOT
            / "prompts"
            / "fixtures"
            / f"{prompt_key}@{version}"
            / f"{self.fixture_case}.json"
        )
        if not fixture.is_file():
            raise LLMError(f"Missing LLM fixture: {fixture.relative_to(REPO_ROOT)}")
        return schema.model_validate_json(fixture.read_text(encoding="utf-8"))


class OpenAICompatibleLLM:
    def __init__(self, settings: Settings) -> None:
        if not settings.llm_network_enabled:
            raise LLMError("Live LLM network access is disabled")
        if not settings.llm_api_key:
            raise LLMError("LLM_API_KEY is required for a live provider")
        self.settings = settings

    async def complete(
        self,
        prompt_key: str,
        version: str,
        variables: dict[str, Any],
        schema: type[SchemaT],
    ) -> SchemaT:
        prompt = load_prompt(prompt_key, version, variables)
        payload = {
            "model": prompt.get("model", self.settings.llm_model),
            "temperature": prompt.get("temperature", 0),
            "messages": [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
            },
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return schema.model_validate(json.loads(content))


def get_llm(settings: Settings | None = None) -> LLMClient:
    resolved = settings or get_settings()
    if resolved.llm_provider == "fake":
        return FakeLLM(resolved.llm_fixture_case)
    return OpenAICompatibleLLM(resolved)

