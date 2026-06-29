import docker
import subprocess
import os
from typing import Dict, Any
from healer.src.config import settings

class DockerExecutor:
    def __init__(self):
        try:
            # Connect to Docker daemon
            self.client = docker.from_env()
        except Exception as e:
            print(f"Failed to connect to local Docker daemon: {e}. Docker actions will be mocked.")
            self.client = None

    def restart_container(self, service: str) -> Dict[str, Any]:
        """
        Restarts a container matching the service name.
        """
        if not self.client:
            return {
                "status": "success",
                "output": f"Docker client disconnected. Mock restarted container for service: '{service}'."
            }

        try:
            # List containers and search for matching name/label
            containers = self.client.containers.list(all=True)
            matched_container = None
            for container in containers:
                if service in container.name:
                    matched_container = container
                    break

            if not matched_container:
                return {
                    "status": "failure",
                    "output": f"No running docker container found matching service name '{service}'."
                }

            print(f"Restarting container: {matched_container.name}...")
            matched_container.restart()
            return {
                "status": "success",
                "output": f"Container {matched_container.name} restarted successfully."
            }
        except Exception as e:
            print(f"Error restarting container {service}: {e}")
            return {
                "status": "failure",
                "output": f"Error restarting container: {str(e)}"
            }

    def scale_replicas(self, service: str, replicas: int = 2) -> Dict[str, Any]:
        """
        Scales a service to the target replicas. Uses docker compose scale command if inside docker compose,
        otherwise uses a mock.
        """
        # If compose file exists in standard places, try to use it
        # Otherwise mock the scale action
        try:
            # Try running command line docker compose scale
            # We look for docker-compose.yml in parent folder (infra)
            infra_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../infra"))
            if os.path.exists(os.path.join(infra_dir, "docker-compose.yml")):
                cmd = f"docker compose -f {infra_dir}/docker-compose.yml up -d --scale {service}={replicas}"
                print(f"Executing compose scale command: {cmd}")
                
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=infra_dir
                )
                
                if result.returncode == 0:
                    return {
                        "status": "success",
                        "output": f"Scaled service '{service}' to {replicas} replicas via docker-compose."
                    }
                else:
                    return {
                        "status": "failure",
                        "output": f"Failed to scale service via compose: {result.stderr}"
                    }
        except Exception as e:
            print(f"Error running docker compose scale: {e}")

        # Fallback/Mock success
        return {
            "status": "success",
            "output": f"Mock scaled service '{service}' to {replicas} replicas."
        }

docker_executor = DockerExecutor()
