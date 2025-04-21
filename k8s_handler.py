# k8s_handler.py
import os
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from datetime import datetime, timezone
import logging # Use logging for better output control

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Kubernetes Config and Client Initialization ---

K8S_CONFIG_LOADED = False # Flag to track if config is loaded

def load_k8s_config():
    """Loads Kubernetes configuration (from default location)."""
    global K8S_CONFIG_LOADED
    if K8S_CONFIG_LOADED:
        return True
    try:
        # Tries loading default config (~/.kube/config) or in-cluster config
        config.load_kube_config()
        logger.info("Successfully loaded Kubernetes configuration.")
        K8S_CONFIG_LOADED = True
        return True
    except config.ConfigException as e1:
        logger.error(f"Error loading Kubernetes configuration: {e1}")
        # Try loading in-cluster config as a fallback (useful if deployed in K8s later)
        try:
            config.load_incluster_config()
            logger.info("Successfully loaded in-cluster Kubernetes configuration.")
            K8S_CONFIG_LOADED = True
            return True
        except config.ConfigException as e2:
            logger.error(f"Could not load default or in-cluster config: {e2}")
            K8S_CONFIG_LOADED = False
            return False
    except Exception as e: # Catch any other potential error during loading
        logger.error(f"An unexpected error occurred loading K8s config: {e}")
        K8S_CONFIG_LOADED = False
        return False

def get_k8s_core_v1_api():
    """Returns an instance of the CoreV1Api client."""
    if not K8S_CONFIG_LOADED:
        if not load_k8s_config(): # Try loading config if not already loaded
             logger.error("Cannot create K8s CoreV1Api client: Config not loaded.")
             return None
    return client.CoreV1Api()

def get_k8s_apps_v1_api():
    """Returns an instance of the AppsV1Api client."""
    if not K8S_CONFIG_LOADED:
        if not load_k8s_config(): # Try loading config if not already loaded
            logger.error("Cannot create K8s AppsV1Api client: Config not loaded.")
            return None
    return client.AppsV1Api()

# --- Helper Function for Age Calculation ---
def _calculate_age(creation_timestamp):
    """Calculates human-readable age from a timestamp."""
    if not creation_timestamp:
        return "N/A"
    now = datetime.now(timezone.utc)
    age = now - creation_timestamp
    days, remainder = divmod(age.total_seconds(), 86400) # 86400 seconds in a day
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days > 0:
        return f"{int(days)}d {int(hours)}h"
    elif hours > 0:
        return f"{int(hours)}h {int(minutes)}m"
    elif minutes > 0:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(seconds)}s"

# --- Kubernetes Actions ---

def get_pods_in_namespace(api: client.CoreV1Api, namespace: str = "default"):
    """Gets formatted list of pods in a specific namespace."""
    if not api:
        return False, "Kubernetes API client not initialized."
    try:
        logger.info(f"Attempting to list pods in namespace: {namespace}")
        pods = api.list_namespaced_pod(namespace=namespace, timeout_seconds=10) # Add timeout

        if not pods.items:
            return True, f"No pods found in namespace `{namespace}`."

        # Format output
        output = ["```"] # Start Slack code block
        header = "{:<40} {:<15} {:<10} {:<10}".format("NAME", "STATUS", "RESTARTS", "AGE")
        output.append(header)
        output.append("-" * len(header)) # Separator

        for pod in pods.items:
            name = pod.metadata.name
            status = pod.status.phase
            restarts = sum(c.restart_count for c in pod.status.container_statuses) if pod.status.container_statuses else 0
            age = _calculate_age(pod.metadata.creation_timestamp)
            output.append("{:<40} {:<15} {:<10} {:<10}".format(name[:39], status, restarts, age)) # Truncate long names

        output.append("```") # End Slack code block
        return True, "\n".join(output)

    except ApiException as e:
        logger.error(f"ApiException listing pods in namespace {namespace}: {e.status} - {e.reason} - {e.body}")
        if e.status == 404:
            return False, f"Error: Namespace `{namespace}` not found."
        elif e.status == 403:
             return False, f"Error: Insufficient permissions to list pods in namespace `{namespace}`."
        else:
            return False, f"Error listing pods in `{namespace}` (API Error {e.status}). Check bot logs."
    except Exception as e:
        logger.error(f"An unexpected error occurred listing pods: {e}", exc_info=True) # Log traceback
        return False, f"An unexpected error occurred while listing pods in `{namespace}`."


def get_deployments_in_namespace(api: client.AppsV1Api, namespace: str = "default"):
    """Gets formatted list of deployments in a specific namespace."""
    if not api:
        return False, "Kubernetes API client not initialized."
    try:
        logger.info(f"Attempting to list deployments in namespace: {namespace}")
        deployments = api.list_namespaced_deployment(namespace=namespace, timeout_seconds=10)

        if not deployments.items:
            return True, f"No deployments found in namespace `{namespace}`."

        # Format output
        output = ["```"]
        header = "{:<40} {:<10} {:<10} {:<10}".format("NAME", "READY", "UP-TO-DATE", "AVAILABLE")
        output.append(header)
        output.append("-" * len(header))

        for dep in deployments.items:
            name = dep.metadata.name
            ready = f"{dep.status.ready_replicas or 0}/{dep.spec.replicas}"
            up_to_date = dep.status.updated_replicas or 0
            available = dep.status.available_replicas or 0
            output.append("{:<40} {:<10} {:<10} {:<10}".format(name[:39], ready, up_to_date, available))

        output.append("```")
        return True, "\n".join(output)

    except ApiException as e:
        logger.error(f"ApiException listing deployments in {namespace}: {e.status} - {e.reason} - {e.body}")
        if e.status == 404:
            return False, f"Error: Namespace `{namespace}` not found."
        elif e.status == 403:
             return False, f"Error: Insufficient permissions to list deployments in namespace `{namespace}`."
        else:
            return False, f"Error listing deployments in `{namespace}` (API Error {e.status}). Check bot logs."
    except Exception as e:
        logger.error(f"An unexpected error occurred listing deployments: {e}", exc_info=True)
        return False, f"An unexpected error occurred while listing deployments in `{namespace}`."


# Example of how to test functions directly (optional)
if __name__ == "__main__":
    print("Attempting to load K8s config for direct testing...")
    if load_k8s_config():
        print("Config loaded.")
        core_v1_api = get_k8s_core_v1_api()
        apps_v1_api = get_k8s_apps_v1_api()

        if core_v1_api:
            print("\n--- Testing Pods (default namespace) ---")
            success_pods, msg_pods = get_pods_in_namespace(core_v1_api, "default")
            print(f"Success: {success_pods}\n{msg_pods}")

            print("\n--- Testing Pods (kube-system namespace) ---")
            success_pods_ks, msg_pods_ks = get_pods_in_namespace(core_v1_api, "kube-system")
            print(f"Success: {success_pods_ks}\n{msg_pods_ks}")

            print("\n--- Testing Pods (non-existent namespace) ---")
            success_pods_ne, msg_pods_ne = get_pods_in_namespace(core_v1_api, "non-existent-ns")
            print(f"Success: {success_pods_ne}\n{msg_pods_ne}")

        if apps_v1_api:
            print("\n--- Testing Deployments (default namespace) ---")
            success_deps, msg_deps = get_deployments_in_namespace(apps_v1_api, "default")
            print(f"Success: {success_deps}\n{msg_deps}")

    else:
        print("Could not load K8s config. Aborting tests.")