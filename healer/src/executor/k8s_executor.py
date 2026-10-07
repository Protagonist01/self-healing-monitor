from typing import Dict, Any

from healer.src.config import settings


class K8sExecutor:
    def __init__(self):
        self._available = False
        self._api = None
        self._apps_v1 = None
        self._try_init()

    def _try_init(self):
        """Attempt to load the Kubernetes client. Falls back to scaffold mode."""
        try:
            from kubernetes import client, config

            try:
                config.load_incluster_config()
            except Exception:
                config.load_kube_config()

            self._api = client.ApiClient()
            self._apps_v1 = client.AppsV1Api(self._api)
            self._available = True
            print("Kubernetes executor initialized successfully.")
        except ImportError:
            print("kubernetes package not installed. K8s executor in scaffold mode.")
        except Exception as e:
            print(f"Kubernetes config not available: {e}. K8s executor in scaffold mode.")

    def is_available(self) -> bool:
        return self._available

    def restart_deployment(self, service: str) -> Dict[str, Any]:
        """
        Performs a rollout restart of a Kubernetes Deployment by patching
        the annotations with a new rollout timestamp.
        """
        if not self._available:
            return {
                "status": "skipped",
                "output": f"Kubernetes executor not available. Skipped restart for deployment '{service}'.",
            }

        try:
            body = {
                "spec": {
                    "template": {
                        "metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": _now()}}
                    }
                }
            }
            self._apps_v1.patch_namespaced_deployment(
                name=service,
                namespace=settings.K8S_NAMESPACE,
                body=body,
            )
            return {
                "status": "success",
                "output": f"Deployment '{service}' rollout restart triggered in namespace '{settings.K8S_NAMESPACE}'.",
            }
        except Exception as e:
            return {
                "status": "failure",
                "output": f"Error restarting deployment '{service}': {str(e)}",
            }

    def scale_deployment(self, service: str, replicas: int = 2) -> Dict[str, Any]:
        """
        Scales a Kubernetes Deployment to the specified replica count.
        """
        if not self._available:
            return {
                "status": "skipped",
                "output": f"Kubernetes executor not available. Skipped scaling deployment '{service}'.",
            }

        try:
            body = {"spec": {"replicas": replicas}}
            self._apps_v1.patch_namespaced_deployment_scale(
                name=service,
                namespace=settings.K8S_NAMESPACE,
                body=body,
            )
            return {
                "status": "success",
                "output": f"Deployment '{service}' scaled to {replicas} replicas in namespace '{settings.K8S_NAMESPACE}'.",
            }
        except Exception as e:
            return {
                "status": "failure",
                "output": f"Error scaling deployment '{service}': {str(e)}",
            }

    def rollback_deployment(self, service: str) -> Dict[str, Any]:
        """
        Rolls back a Kubernetes Deployment to the previous revision.
        """
        if not self._available:
            return {
                "status": "skipped",
                "output": f"Kubernetes executor not available. Skipped rollback for deployment '{service}'.",
            }

        try:
            # Modern AppsV1Api has no rollback endpoint; kubectl applies the revision.
            import subprocess

            result = subprocess.run(
                [
                    "kubectl",
                    "rollout",
                    "undo",
                    f"deployment/{service}",
                    "-n",
                    settings.K8S_NAMESPACE,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return {
                    "status": "success",
                    "output": f"Deployment '{service}' rolled back to previous revision.",
                }
            else:
                return {"status": "failure", "output": f"kubectl rollback failed: {result.stderr}"}
        except Exception as e:
            return {
                "status": "failure",
                "output": f"Error rolling back deployment '{service}': {str(e)}",
            }


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


k8s_executor = K8sExecutor()
