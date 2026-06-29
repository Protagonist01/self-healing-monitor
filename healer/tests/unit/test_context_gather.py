from healer.src.agent.nodes import context_gather


class FakeIndexer:
    def __init__(self):
        self.indexed = False

    def index_runbooks(self):
        self.indexed = True

    def search(self, query, limit=1):
        assert "HighMemoryUsage" in query
        return [
            {
                "metadata": {"source": "high_memory.md"},
                "document": "Runbook: high_memory.md\nContent:\nRestart the container."
            }
        ]


def test_context_gather_assembles_metrics_logs_deploys_and_runbook(monkeypatch, base_state):
    fake_indexer = FakeIndexer()
    monkeypatch.setattr(context_gather, "indexer", fake_indexer)
    monkeypatch.setattr(context_gather, "get_keyword_runbook", lambda alert_name, log_summary: {})
    monkeypatch.setattr(
        context_gather,
        "get_prometheus_metrics",
        lambda service, alert_name: {
            "metrics_summary": "memory at 94%",
            "metrics_raw": [{"value": [1, "94"]}],
        },
    )
    monkeypatch.setattr(
        context_gather,
        "get_loki_logs",
        lambda service: {
            "log_lines_count": 1,
            "log_summary": "OOMKilled detected",
            "log_raw": ["OOMKilled"],
        },
    )
    monkeypatch.setattr(
        context_gather,
        "get_recent_deploys",
        lambda service: ["v2.4.1 deployed 47 minutes ago"],
    )

    state = context_gather.context_gather_node(base_state)

    assert fake_indexer.indexed is True
    assert state["context"]["metrics_summary"] == "memory at 94%"
    assert state["context"]["log_lines_count"] == 1
    assert state["context"]["recent_deploys"] == ["v2.4.1 deployed 47 minutes ago"]
    assert state["context"]["runbook_matched"] == "high_memory.md"


def test_keyword_runbook_prefers_memory_runbook():
    match = context_gather.get_keyword_runbook("HighMemoryUsage", "OOMKilled detected")

    assert match["runbook_matched"] == "high_memory.md"
    assert "memory" in match["runbook_excerpt"].lower()
