"""
Integration tests for the Docker executor service allowlist.

These tests verify that the Docker executor enforces the DOCKER_ALLOWED_SERVICES
allowlist, and that restart/scale operations are correctly gated.
"""

from unittest.mock import patch, MagicMock
from healer.src.executor.docker_executor import DockerExecutor


def test_docker_executor_allows_listed_service():
    """When DOCKER_ALLOWED_SERVICES is set, only listed services are allowed."""
    with patch("healer.src.executor.docker_executor.settings") as mock_settings:
        mock_settings.DOCKER_ALLOWED_SERVICES = "leaky_service,flaky_service"
        executor = DockerExecutor()
        assert executor._is_service_allowed("leaky_service") is True
        assert executor._is_service_allowed("flaky_service") is True
        assert executor._is_service_allowed("evil_service") is False


def test_docker_executor_denies_all_when_no_allowlist():
    """When DOCKER_ALLOWED_SERVICES is empty, all services are denied."""
    with patch("healer.src.executor.docker_executor.settings") as mock_settings:
        mock_settings.DOCKER_ALLOWED_SERVICES = ""
        executor = DockerExecutor()
        assert executor._is_service_allowed("anything") is False
        assert executor._is_service_allowed("leaky_service") is False


def test_docker_restart_denied_for_unlisted_service():
    """Restart returns failure for services not in the allowlist."""
    with patch("healer.src.executor.docker_executor.settings") as mock_settings:
        mock_settings.DOCKER_ALLOWED_SERVICES = "leaky_service"
        executor = DockerExecutor()
        executor.client = None  # avoid real Docker connection
        result = executor.restart_container("evil_service")
        assert result["status"] == "failure"
        assert "allowlist" in result["output"]


def test_docker_scale_denied_for_unlisted_service():
    """Scale returns failure for services not in the allowlist."""
    with patch("healer.src.executor.docker_executor.settings") as mock_settings:
        mock_settings.DOCKER_ALLOWED_SERVICES = "leaky_service"
        executor = DockerExecutor()
        executor.client = None
        result = executor.scale_replicas("evil_service", replicas=3)
        assert result["status"] == "failure"
        assert "allowlist" in result["output"]


def test_docker_restart_failure_when_disconnected():
    with (
        patch("healer.src.executor.docker_executor.settings") as config,
        patch("docker.DockerClient", side_effect=RuntimeError("disconnected")),
    ):
        config.DOCKER_ALLOWED_SERVICES = "leaky_service"
        result = DockerExecutor().restart_container("leaky_service")
        assert result["status"] == "failure"


def test_docker_restart_exact_name_only():
    with patch("healer.src.executor.docker_executor.settings") as config:
        config.DOCKER_ALLOWED_SERVICES = "leaky_service"
        executor = DockerExecutor()
        executor.client = MagicMock()
        container = executor.client.containers.get.return_value
        container.name = "prefix-leaky_service"
        assert executor.restart_container("leaky_service")["status"] == "failure"
        container.restart.assert_not_called()
        container.name = "leaky_service"
        assert executor.restart_container("leaky_service")["status"] == "success"
        container.restart.assert_called_once_with(timeout=10)
