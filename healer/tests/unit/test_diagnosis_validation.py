from types import SimpleNamespace
from unittest.mock import patch

import pytest

from healer.src.agent.nodes.diagnose import diagnose_node
from healer.src.config import settings


@pytest.mark.parametrize(
    "response",
    [
        '{"root_cause":"memory leak","confidence":2,"supporting_evidence":[]}',
        '{"root_cause":"memory leak","confidence":NaN,"supporting_evidence":[]}',
        '{"root_cause":"memory leak","confidence":0.9,"supporting_evidence":"invented"}',
        "not JSON",
    ],
)
def test_invalid_provider_response_cannot_authorize_action(base_state, response):
    base_state["context"] = {
        "metrics_summary": "Memory high",
        "log_summary": "Logs unavailable",
        "runbook_excerpt": "Restart only after review",
    }
    answer = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=response))], usage=None
    )
    with (
        patch.object(settings, "OPENROUTER_API_KEY", "test-key"),
        patch("healer.src.agent.nodes.diagnose.OpenAI") as provider,
    ):
        provider.return_value.chat.completions.create.return_value = answer
        result = diagnose_node(base_state)
    assert result["diagnosis"]["confidence"] == 0
    assert result["diagnosis"]["supporting_evidence"] == []
