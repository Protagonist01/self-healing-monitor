from healer.src.main import is_firing_alert


def test_firing_alert_is_processed():
    assert is_firing_alert("firing", {"status": "firing"}) is True


def test_resolved_payload_is_ignored():
    assert is_firing_alert("resolved", {"labels": {"alertname": "HighMemoryUsage"}}) is False


def test_resolved_alert_is_ignored_even_when_payload_is_firing():
    assert is_firing_alert("firing", {"status": "resolved"}) is False
