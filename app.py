# app.py
import os
import time # Keep for potential delays if needed, but Jenkins calls might be quick
import random # Can remove random now
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request, Response # Response needed for ack()

# --- Import your Jenkins Handler ---
import jenkins_handler
import jenkins # Import the jenkins library to catch its exceptions
import k8s_handler # Import Kubernetes handler
from kubernetes import client
import docker_handler # Import Docker handler
from docker.errors import DockerException # Import Docker exception

# Load environment variables from .env file
load_dotenv()

# Initialize Slack Bolt app
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Initialize Jenkins client (or handle potential errors)
try:
    jenkins_client = jenkins_handler.get_jenkins_client()
except ValueError as e:
    print(f"ERROR: Configuration error - {e}")
    # Decide how to handle this - maybe the bot can't start?
    # For now, we'll print and set client to None
    jenkins_client = None
except jenkins.JenkinsException as e:
    print(f"ERROR: Could not connect to Jenkins on startup - {e}")
    jenkins_client = None # Bot can start but Jenkins commands will fail

# --- Initialize Kubernetes Clients ---
k8s_core_v1_api = None
k8s_apps_v1_api = None
if k8s_handler.load_k8s_config(): # Try loading K8s config on startup
    k8s_core_v1_api = k8s_handler.get_k8s_core_v1_api()
    k8s_apps_v1_api = k8s_handler.get_k8s_apps_v1_api()
    if not k8s_core_v1_api or not k8s_apps_v1_api:
        print("ERROR: Failed to initialize Kubernetes API clients after successful config load.")
else:
    print("WARNING: Kubernetes configuration could not be loaded. K8s commands will fail.")

# --- Initialize Docker Client ---
docker_client = None
try:
    # Attempt to get the client on startup
    docker_client = docker_handler.get_docker_client()
except Exception as e: # Catch potential errors during module loading/init
     print(f"ERROR: Could not initialize Docker client on startup - {e}")

# === Mention Handler (keep as before) ===
@app.event("app_mention")
def handle_app_mention_events(body, say, logger):
    logger.info("Received app_mention event")
    message_text = body["event"]["text"]
    user_id = body["event"]["user"]
    response_text = f"Hi <@{user_id}>! You mentioned me. You said: '{message_text}'"
    say(response_text)


# === Slash Command Handlers ===

@app.command("/jenkins-trigger")
def handle_jenkins_trigger_command(ack, body, command, respond, logger):
    """ Handles the /jenkins-trigger command """
    ack() # Acknowledge immediately
    logger.info(f"Received /jenkins-trigger command: {command}")
    job_name = command.get('text', '').strip()

    if not job_name:
        respond("Please provide the Jenkins job name. Usage: `/jenkins-trigger [job_name]`")
        return

    if not jenkins_client:
         respond("Sorry, the connection to Jenkins is not configured or failed. Please check the bot logs.")
         return

    logger.info(f"Attempting to trigger Jenkins job: {job_name}")
    # Call the actual Jenkins handler function
    success, message = jenkins_handler.trigger_jenkins_job(jenkins_client, job_name)

    # Send the result back using respond
    if success:
        logger.info(f"Successfully triggered job {job_name}. Message: {message}")
        respond(f":rocket: {message}") # Use respond for delayed messages
    else:
        logger.error(f"Failed to trigger job {job_name}. Message: {message}")
        respond(f":x: {message}")


@app.command("/jenkins-status")
def handle_jenkins_status_command(ack, body, command, respond, logger):
    """ Handles the /jenkins-status command """
    ack()
    logger.info(f"Received /jenkins-status command: {command}")
    job_name = command.get('text', '').strip()

    if not job_name:
        respond("Please provide the Jenkins job name. Usage: `/jenkins-status [job_name]`")
        return

    if not jenkins_client:
         respond("Sorry, the connection to Jenkins is not configured or failed. Please check the bot logs.")
         return

    logger.info(f"Attempting to get status for Jenkins job: {job_name}")
    # Call the actual Jenkins handler function
    success, message = jenkins_handler.get_job_status(jenkins_client, job_name)

    if success:
        logger.info(f"Successfully retrieved status for {job_name}. Message: {message}")
        # Respond with the formatted status message
        respond(f":information_source: {message}")
    else:
        logger.error(f"Failed to get status for {job_name}. Message: {message}")
        respond(f":x: {message}")

# === Kubernetes Slash Command Handlers ===
@app.command("/k8s-pods")
def handle_k8s_pods_command(ack, body, command, respond, logger):
    """ Handles the /k8s-pods command """
    ack()
    logger.info(f"Received /k8s-pods command: {command}")
    namespace = command.get('text', 'default').strip() # Default to 'default' namespace if none provided
    if not namespace: # Handle case where user types space then nothing
        namespace = "default"

    if not k8s_core_v1_api:
        respond("Sorry, the connection to Kubernetes is not configured or failed. Please check bot logs.")
        return

    logger.info(f"Attempting to list pods in namespace: {namespace}")
    # Call the actual K8s handler function
    success, message = k8s_handler.get_pods_in_namespace(k8s_core_v1_api, namespace)

    if success:
        logger.info(f"Successfully listed pods in namespace {namespace}.")
        respond(f":kubernetes: Pods in namespace `{namespace}`:\n{message}")
    else:
        logger.error(f"Failed to list pods in namespace {namespace}. Message: {message}")
        respond(f":x: {message}")


@app.command("/k8s-deployments")
def handle_k8s_deployments_command(ack, body, command, respond, logger):
    """ Handles the /k8s-deployments command """
    ack()
    logger.info(f"Received /k8s-deployments command: {command}")
    namespace = command.get('text', 'default').strip()
    if not namespace:
        namespace = "default"

    if not k8s_apps_v1_api:
        respond("Sorry, the connection to Kubernetes is not configured or failed. Please check bot logs.")
        return

    logger.info(f"Attempting to list deployments in namespace: {namespace}")
    # Call the actual K8s handler function
    success, message = k8s_handler.get_deployments_in_namespace(k8s_apps_v1_api, namespace)

    if success:
        logger.info(f"Successfully listed deployments in namespace {namespace}.")
        respond(f":kubernetes: Deployments in namespace `{namespace}`:\n{message}")
    else:
        logger.error(f"Failed to list deployments in namespace {namespace}. Message: {message}")
        respond(f":x: {message}")

# === Docker Slash Command Handler ===
@app.command("/docker-ps")
def handle_docker_ps_command(ack, body, command, respond, logger):
    """ Handles the /docker-ps command """
    ack() # Acknowledge immediately
    logger.info(f"Received /docker-ps command: {command}")

    # Check if the docker client was initialized successfully
    if not docker_client:
        respond("Sorry, the connection to the Docker daemon failed on startup or is not configured. Please check bot logs.")
        return

    logger.info("Attempting to list running Docker containers.")
    # Call the actual Docker handler function
    success, message = docker_handler.list_running_containers(docker_client)

    if success:
        logger.info("Successfully listed running Docker containers.")
        respond(f":docker: Running Containers:\n{message}")
    else:
        logger.error(f"Failed to list Docker containers. Message: {message}")
        respond(f":x: {message}")

@app.command("/jenkins-log")
def handle_jenkins_log_command(ack, body, command, respond, logger):
    ack()
    job_name = command.get('text', '').strip()
    if not job_name:
        respond("Usage: `/jenkins-log [job_name]`")
        return

    success, message = jenkins_handler.get_last_build_log(jenkins_client, job_name)
    respond(message)

@app.command("/docker-logs")
def handle_docker_logs_command(ack, body, command, respond, logger):
    ack()
    container_name = command.get('text', '').strip()
    if not container_name:
        respond("Usage: `/docker-logs [container_name]`")
        return

    success, message = docker_handler.get_container_logs(docker_client, container_name)
    respond(message)

@app.command("/k8s-restart-deployment")
def handle_k8s_restart_deployment_command(ack, body, command, respond, logger):
    ack()
    parts = command.get('text', '').strip().split()
    if len(parts) == 0:
        respond("Usage: `/k8s-restart-deployment <deployment-name> [namespace]`")
        return

    name = parts[0]
    namespace = parts[1] if len(parts) > 1 else "default"
    # print("jjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj")
    # print(k8s_apps_v1_api, name, namespace)
    success, message = k8s_handler.restart_deployment(k8s_apps_v1_api, name, namespace)
    respond(message)


# === Flask Setup (keep as before) ===
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

if __name__ == "__main__":
    if not jenkins_client:
        print("\nWARNING: Jenkins client not initialized. Jenkins commands will fail.\n")
    if not k8s_core_v1_api or not k8s_apps_v1_api:
         print("\nWARNING: Kubernetes client not initialized/config failed. K8s commands will fail.\n")
    if not docker_client:
         print("\nWARNING: Docker client not initialized. Docker commands will fail.\n")

    port = int(os.environ.get("PORT", 3000))
    flask_app.run(host="0.0.0.0", port=port, debug=True)