import pytest

import fact_check_pipeline
from hooks import safety_hooks
from memory_tools import memory_server


@pytest.mark.asyncio
async def test_main_configures_scoped_agents_permissions_memory_and_hooks(monkeypatch):
    captured = {}

    def capture_options(**options):
        captured["options"] = options
        return options

    class FakeClient:
        def __init__(self, options):
            captured["client_options"] = options

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return None

        async def query(self, prompt):
            captured["prompt"] = prompt

        async def receive_response(self):
            if False:
                yield None

    monkeypatch.setattr(fact_check_pipeline, "ClaudeAgentOptions", capture_options)
    monkeypatch.setattr(fact_check_pipeline, "ClaudeSDKClient", FakeClient)

    await fact_check_pipeline.main()

    options = captured["options"]
    assert options["agents"] == {
        "researcher": fact_check_pipeline.researcher,
        "fact-checker": fact_check_pipeline.fact_checker,
    }
    assert options["agents"]["researcher"].tools == ["WebSearch"]
    assert options["agents"]["fact-checker"].tools == ["WebSearch"]
    assert options["permission_mode"] == "dontAsk"
    assert options["disallowed_tools"] == ["Bash", "Write", "Edit", "WebFetch"]
    assert options["mcp_servers"] == {"memory-tools": memory_server}
    assert options["hooks"] is safety_hooks
    assert options["setting_sources"] == ["project"]
    assert captured["client_options"] is options
    assert captured["prompt"] == "Topic: Taj Mahal"
