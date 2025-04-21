# docker_handler.py
import docker
from docker.errors import DockerException
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Docker Client Initialization ---
def get_docker_client():
    """
    Initializes and returns a Docker client instance connected via the default socket/pipe.
    Returns None if connection fails.
    """
    try:
        # Connects using the default socket or named pipe (most common)
        # For remote daemons, use docker.DockerClient(base_url='tcp://host:port')
        client = docker.from_env()
        # Test the connection
        client.ping()
        logger.info("Successfully connected to Docker daemon.")
        return client
    except DockerException as e:
        logger.error(f"Error connecting to Docker daemon: {e}")
        logger.error("Please ensure the Docker daemon is running and accessible.")
        return None
    except Exception as e: # Catch other potential errors during initialization
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


# Example of how to test functions directly (optional)
if __name__ == "__main__":
    print("Attempting to connect to Docker for direct testing...")
    docker_client = get_docker_client()

    if docker_client:
        print("\n--- Testing Container List ---")
        success, message = list_running_containers(docker_client)
        print(f"Success: {success}\n{message}")
    else:
        print("Could not connect to Docker daemon. Aborting tests.")