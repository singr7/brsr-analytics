from pathlib import Path

import pytest
from pydantic import BaseModel

from api.app.core.config import Settings
from api.app.services.llm import FakeLLM, LLMError, OpenAICompatibleLLM, get_llm


class DemoSummary(BaseModel):
    summary: str
    confidence: float


async def test_fake_llm_round_trip_is_offline() -> None:
    result = await FakeLLM().complete(
        "demo_summary",
        "v1",
        {"disclosure": "Energy intensity fell 8%."},
        DemoSummary,
    )
    assert result.confidence == 0.99
    assert "energy intensity" in result.summary


async def test_fake_llm_requires_committed_fixture() -> None:
    with pytest.raises(LLMError, match="Missing LLM fixture"):
        await FakeLLM("not-committed").complete(
            "demo_summary", "v1", {"disclosure": "x"}, DemoSummary
        )


def test_live_client_is_disabled_by_default() -> None:
    with pytest.raises(LLMError, match="disabled"):
        OpenAICompatibleLLM(
            Settings(
                llm_provider="live",
                llm_api_key="secret",
                llm_network_enabled=False,
            )
        )


def test_factory_selects_fake() -> None:
    assert isinstance(get_llm(Settings(llm_provider="fake")), FakeLLM)


async def test_live_client_uses_environment_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"summary":"configured model","confidence":0.99}'
                        }
                    }
                ]
            }

    class Client:
        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: object) -> Response:
            captured["url"] = url
            captured["payload"] = kwargs["json"]
            return Response()

    monkeypatch.setattr("api.app.services.llm.httpx.AsyncClient", lambda **kwargs: Client())
    client = OpenAICompatibleLLM(
        Settings(
            llm_provider="openai",
            llm_api_key="secret",
            llm_network_enabled=True,
            llm_model="configured-model",
        )
    )
    result = await client.complete(
        "demo_summary",
        "v1",
        {"disclosure": "Energy intensity fell 8%."},
        DemoSummary,
    )

    assert result.summary == "configured model"
    assert isinstance(captured["payload"], dict)
    assert captured["payload"]["model"] == "configured-model"


def test_prompt_fixture_naming_contract() -> None:
    fixture = Path("prompts/fixtures/demo_summary@v1/default.json")
    assert fixture.is_file()
