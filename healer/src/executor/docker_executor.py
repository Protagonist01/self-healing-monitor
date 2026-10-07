"""Docker operations restricted to explicitly named containers."""

from typing import Any, Dict
import docker
from healer.src.config import settings


class DockerExecutor:
    def __init__(self):
        self._allowed_services = self._parse_allowed_services()
        self.client = None

    def _parse_allowed_services(self):
        return {s.strip() for s in settings.DOCKER_ALLOWED_SERVICES.split(",") if s.strip()}

    def _is_service_allowed(self, service: str) -> bool:
        return bool(service) and service in self._allowed_services

    def restart_container(self, service: str) -> Dict[str, Any]:
        if not self._is_service_allowed(service):
            return {
                "status": "failure",
                "output": f"Service '{service}' is not in the DOCKER_ALLOWED_SERVICES allowlist. Action denied.",
            }
        try:
            if self.client is None:
                self.client = docker.DockerClient(base_url=settings.DOCKER_HOST, timeout=15)
            container = self.client.containers.get(service)
            # Docker accepts IDs and prefixes too; authorize exact names only.
            if container.name != service:
                return {
                    "status": "failure",
                    "output": "Docker target did not match the authorized container name.",
                }
            container.restart(timeout=10)
            return {"status": "success", "output": f"Container {service} restarted successfully."}
        except Exception as exc:
            return {"status": "failure", "output": f"Docker restart failed: {exc}"}

    def scale_replicas(self, service: str, replicas: int = 2) -> Dict[str, Any]:
        if not self._is_service_allowed(service):
            return {
                "status": "failure",
                "output": f"Service '{service}' is not in the DOCKER_ALLOWED_SERVICES allowlist. Action denied.",
            }
        return {
            "status": "skipped",
            "output": "Scaling is unsupported for this Docker deployment. Use your deployment tooling.",
        }


docker_executor = DockerExecutor()
