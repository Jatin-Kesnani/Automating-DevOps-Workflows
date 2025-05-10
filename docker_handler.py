# docker_handler.py
import docker
from docker.errors import DockerException
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Docker Client Initialization ---
def get_docker_client():
    """
    Initializes and returns a Docker client instance with proper TLS configuration.
    Supports both local and remote Docker daemons.
    Returns None if connection fails.
    """
    try:
        # Get Docker configuration from environment variables
        docker_host = os.environ.get('DOCKER_HOST', 'unix://var/run/docker.sock')
        tls_verify = os.environ.get('DOCKER_TLS_VERIFY', '0').lower() in ('1', 'true', 'yes')
        cert_path = os.environ.get('DOCKER_CERT_PATH')
        
        # Configure TLS if required
        tls_config = None
        if tls_verify and cert_path:
            cert_path = Path(cert_path)
            tls_config = docker.tls.TLSConfig(
                client_cert=(cert_path / 'cert.pem', cert_path / 'key.pem'),
                ca_cert=cert_path / 'ca.pem',
                verify=True
            )
        
        # Initialize client with appropriate configuration
        if docker_host.startswith('unix://'):
            # Local Docker daemon
            client = docker.from_env()
        else:
            # Remote Docker daemon
            client = docker.DockerClient(
                base_url=docker_host,
                tls=tls_config
            )
        
        # Test the connection
        client.ping()
        logger.info(f"Successfully connected to Docker daemon at {docker_host}")
        return client
        
    except DockerException as e:
        logger.error(f"Error connecting to Docker daemon: {e}")
        logger.error("Please ensure the Docker daemon is running and accessible.")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred initializing Docker client: {e}")
        return None

# --- Docker Actions ---
def list_running_containers(client: docker.DockerClient):
    """Gets a formatted list of running Docker containers."""
    if not client:
        return False, "Docker client not initialized. Cannot list containers."
    try:
        logger.info("Attempting to list running Docker containers.")
        containers = client.containers.list()

        if not containers:
            return True, "No running Docker containers found."

        # Format output
        output = ["```"] # Start Slack code block
        # Adjust widths as needed based on typical container IDs/names
        header = "{:<15} {:<30} {:<25} {:<25}".format("CONTAINER ID", "IMAGE", "STATUS", "NAMES")
        output.append(header)
        output.append("-" * len(header)) # Separator

        for container in containers:
            container_id = container.short_id
            image = container.image.tags[0] if container.image.tags else container.image.short_id[:12] # Prefer tag, fallback to image ID
            status = container.status
            name = container.name
            # Ensure columns don't exceed width too much
            output.append("{:<15} {:<30} {:<25} {:<25}".format(
                container_id,
                image[:29], # Truncate long image names/tags
                status[:24],
                name[:24]
            ))

        output.append("```") # End Slack code block
        return True, "\n".join(output)

    except DockerException as e:
        logger.error(f"DockerException while listing containers: {e}")
        return False, f"Error listing containers: Could not communicate with Docker daemon. ({e})"
    except Exception as e:
        logger.error(f"An unexpected error occurred listing containers: {e}", exc_info=True)
        return False, "An unexpected error occurred while listing Docker containers."

def get_container_logs(client: docker.DockerClient, container_name: str, lines=50):
    """Returns last N lines of logs from a specific Docker container."""
    try:
        container = client.containers.get(container_name)
        logs = container.logs(tail=lines).decode("utf-8")
        return True, f"Logs from `{container_name}`:\n```{logs}```"
    except docker.errors.NotFound:
        return False, f"Container `{container_name}` not found."
    except Exception as e:
        return False, f"Error retrieving logs: {str(e)}"

def get_recent_logs(client, container_id=None, max_lines=100):
    """
    Get recent logs from Docker containers.
    If container_id is provided, gets logs for that specific container.
    Otherwise, gets logs from all running containers.
    """
    try:
        if not client:
            return False, "Docker client not initialized"
        
        if container_id:
            # Get logs for specific container
            try:
                container = client.containers.get(container_id)
                logs = container.logs(tail=max_lines, timestamps=True).decode('utf-8')
                return True, logs
            except docker.errors.NotFound:
                return False, f"Container {container_id} not found. Use '/docker-ps' to see available containers."
            except docker.errors.APIError as e:
                return False, f"Error getting logs for container {container_id}: {str(e)}"
        else:
            # Get logs from all running containers
            containers = client.containers.list()
            if not containers:
                return False, "No running containers found. To start a sample container, you can use:\n```docker run -d --name my-nginx nginx```"
            
            all_logs = []
            for container in containers:
                try:
                    logs = container.logs(tail=max_lines, timestamps=True).decode('utf-8')
                    all_logs.append(f"=== Container: {container.name} ({container.id[:12]}) ===\n{logs}")
                except docker.errors.APIError as e:
                    all_logs.append(f"=== Container: {container.name} ({container.id[:12]}) ===\nError getting logs: {str(e)}")
            
            if not all_logs:
                return False, "No logs found in any containers. The containers might be too new or not generating logs yet."
            
            return True, "\n\n".join(all_logs)
            
    except Exception as e:
        logger.error(f"Error getting Docker logs: {str(e)}")
        return False, f"Error getting logs: {str(e)}"