import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler # ADD

import jenkins_handler
import jenkins # Import the jenkins library to catch its exceptions
import k8s_handler
from kubernetes import client # Keep for type hints and exceptions
import docker_handler
from docker.errors import DockerException # Import Docker exception
import requests # For Prometheus
from prometheus_handler import query_prometheus

import threading
import time
from slack_sdk import WebClient

# Load environment variables from .env file
load_dotenv()
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL")

# Initialize Slack Bolt app (this part remains the same)
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET") # Signing secret still used for some features
)

# --- Client Initializations (keep as is) ---
# Initialize Jenkins client
jenkins_client = None
try:
    jenkins_client = jenkins_handler.get_jenkins_client()
except ValueError as e:
    print(f"ERROR: Jenkins Configuration error - {e}")
except jenkins.JenkinsException as e:
    print(f"ERROR: Could not connect to Jenkins on startup - {e}")

# Initialize Kubernetes Clients
k8s_core_v1_api = None
k8s_apps_v1_api = None
if k8s_handler.load_k8s_config():
    k8s_core_v1_api = k8s_handler.get_k8s_core_v1_api()
    k8s_apps_v1_api = k8s_handler.get_k8s_apps_v1_api()
    if not k8s_core_v1_api or not k8s_apps_v1_api:
        print("ERROR: Failed to initialize Kubernetes API clients after successful config load.")
else:
    print("WARNING: Kubernetes configuration could not be loaded. K8s commands will fail.")

# Initialize Docker Client
docker_client = None
try:
    docker_client = docker_handler.get_docker_client()
except Exception as e:
    print(f"ERROR: Could not initialize Docker client on startup - {e}")


# === Event Handlers (like app_mention) and Command Handlers remain THE SAME ===
# Your @app.event("app_mention") and all @app.command(...) handlers
# do not need to change for Socket Mode.

@app.event("app_mention")
def handle_app_mention_events(body, say, logger):
    # ... (Your existing code) ...
    logger.info("Received app_mention event")
    message_text = body["event"]["text"]
    user_id = body["event"]["user"]
    response_text = f"Hi <@{user_id}>! You mentioned me. You said: '{message_text}'"
    say(response_text)

@app.command("/jenkins-trigger")
def handle_jenkins_trigger_command(ack, body, command, respond, logger):
    # ... (Your existing code, ensure it calls ack() first) ...
    ack()
    logger.info(f"Received /jenkins-trigger command: {command}")
    # Assuming your parameter parsing logic from my previous example is here
    # For brevity, showing simplified version from your paste
    args_text = command.get('text', '').strip()
    args_list = args_text.split(maxsplit=1)
    job_name = args_list[0] if len(args_list) > 0 else None
    params_text = args_list[1] if len(args_list) > 1 else ""
    
    if not job_name:
        respond("Please provide the Jenkins job name. Usage: `/jenkins-trigger <job_name> [param1=value1 ...]`")
        return

    if not jenkins_client:
         respond("Sorry, the connection to Jenkins is not configured or failed. Please check the bot logs.")
         return

    job_params = {}
    if params_text:
        try:
            raw_params = params_text.split()
            for param in raw_params:
                if '=' in param:
                    key, value = param.split('=', 1)
                    job_params[key.strip()] = value.strip()
                else:
                    logger.warning(f"Ignoring malformed parameter: {param}")
        except Exception as e:
            logger.error(f"Error parsing parameters: {e}", exc_info=True)
            respond(f":warning: Could not parse parameters: '{params_text}'. Use `key=value` format.")
            job_params = {} # Reset or decide to fail

    success, message = jenkins_handler.trigger_jenkins_job(jenkins_client, job_name, job_params if job_params else None)
    if success: respond(f":rocket: {message}")
    else: respond(f":x: {message}")


@app.command("/jenkins-status")
def handle_jenkins_status_command(ack, body, command, respond, logger):
    # ... (Your existing code) ...
    ack()
    logger.info(f"Received /jenkins-status command: {command}")
    job_name = command.get('text', '').strip()
    if not job_name: respond("Please provide the Jenkins job name. Usage: `/jenkins-status [job_name]`"); return
    if not jenkins_client: respond("Sorry, Jenkins connection failed. Check logs."); return
    success, message = jenkins_handler.get_job_status(jenkins_client, job_name)
    if success: respond(f":information_source: {message}")
    else: respond(f":x: {message}")

@app.command("/k8s-pods")
def handle_k8s_pods_command(ack, body, command, respond, logger):
    # ... (Your existing code) ...
    ack()
    logger.info(f"Received /k8s-pods command: {command}")
    namespace = command.get('text', 'default').strip() or "default"
    if not k8s_core_v1_api: respond("Sorry, K8s connection failed. Check logs."); return
    success, message = k8s_handler.get_pods_in_namespace(k8s_core_v1_api, namespace)
    if success: respond(f":kubernetes: Pods in `{namespace}`:\n{message}")
    else: respond(f":x: {message}")

@app.command("/k8s-deployments")
def handle_k8s_deployments_command(ack, body, command, respond, logger):
    # ... (Your existing code) ...
    ack()
    logger.info(f"Received /k8s-deployments command: {command}")
    namespace = command.get('text', 'default').strip() or "default"
    if not k8s_apps_v1_api: respond("Sorry, K8s connection failed. Check logs."); return
    success, message = k8s_handler.get_deployments_in_namespace(k8s_apps_v1_api, namespace)
    if success: respond(f":kubernetes: Deployments in `{namespace}`:\n{message}")
    else: respond(f":x: {message}")

@app.command("/docker-ps")
def handle_docker_ps_command(ack, body, command, respond, logger):
    # ... (Your existing code) ...
    ack()
    logger.info(f"Received /docker-ps command: {command}")
    if not docker_client: respond("Sorry, Docker connection failed. Check logs."); return
    success, message = docker_handler.list_running_containers(docker_client)
    if success: respond(f":docker: Running Containers:\n{message}")
    else: respond(f":x: {message}")

@app.command("/jenkins-log") # This was in your provided code
def handle_jenkins_log_command(ack, body, command, respond, logger):
    ack()
    logger.info(f"Received /jenkins-log command: {command}")
    # Assuming your command text parsing for job_name and optional build_number
    args_text = command.get('text', '').strip()
    args_list = args_text.split(maxsplit=1)
    job_name = args_list[0] if len(args_list) > 0 else None
    build_number_str = args_list[1] if len(args_list) > 1 else 'lastBuild'

    if not job_name:
        respond("Usage: /jenkins-log <job_name> [build_number|lastBuild]")
        return
    if not jenkins_client: respond("Sorry, Jenkins connection failed. Check logs."); return
    # Assuming get_build_log exists in your jenkins_handler.py and handles 'lastBuild'
    success, message = jenkins_handler.get_build_log(jenkins_client, job_name, build_number_str)
    if success: respond(f":scroll: {message}")
    else: respond(f":x: {message}")


@app.command("/docker-logs") # From your provided code
def handle_docker_logs_command(ack, body, command, respond, logger):
    ack()
    logger.info(f"Received /docker-logs command: {command}")
    container_name = command.get('text', '').strip()
    if not container_name:
        respond("Usage: /docker-logs [container_name]")
        return
    if not docker_client: respond("Sorry, Docker connection failed. Check logs."); return
    # Assuming get_container_logs exists in your docker_handler.py
    success, message = docker_handler.get_container_logs(docker_client, container_name) # You'll need to implement this
    if success: respond(f":scroll: {message}")
    else: respond(f":x: {message}")


@app.command("/k8s-restart-deployment") # From your provided code
def handle_k8s_restart_deployment_command(ack, body, command, respond, logger):
    ack()
    logger.info(f"Received /k8s-restart-deployment command: {command}")
    parts = command.get('text', '').strip().split()
    if len(parts) == 0:
        respond("Usage: /k8s-restart-deployment <deployment-name> [namespace]")
        return
    name = parts[0]
    namespace = parts[1] if len(parts) > 1 else "default"
    if not k8s_apps_v1_api: respond("Sorry, K8s connection failed. Check logs."); return
    # Assuming restart_deployment exists in your k8s_handler.py
    success, message = k8s_handler.restart_deployment(k8s_apps_v1_api, name, namespace) # You'll need to implement this
    if success: respond(f":arrows_counterclockwise: {message}")
    else: respond(f":x: {message}")


@app.command("/monitor-status") # From your provided code
def handle_monitor_status(ack, command, respond, logger):
    ack()
    logger.info(f"Received /monitor-status command: {command}")
    if not PROMETHEUS_URL:
        respond("Prometheus URL not configured. Please set PROMETHEUS_URL in .env")
        return
    try:
        queries = {
            "Jenkins Failures (5m)": 'sum(rate(jenkins_job_last_build_result{result="FAILURE"}[5m]))', # May need Jenkins Prometheus plugin
            "Pod Restarts (10m)": 'sum(increase(kube_pod_container_status_restarts_total[10m]))',
            "Running Containers (Swarm)": 'count(container_last_seen{container_label_com_docker_swarm_service_name!=""})', # This is for Swarm
            "Total K8s Pods": 'count(kube_pod_info)', # Example generic K8s query
        }
        results = []
        for label, query in queries.items():
            # Use a timeout for requests
            res = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=10)
            res.raise_for_status() # Raise an exception for HTTP errors
            data = res.json().get('data', {}).get('result', [])
            value = float(data[0]['value'][1]) if data and len(data) > 0 and len(data[0].get('value', [])) > 1 else 0
            results.append(f"• *{label}*: `{value:.2f}`") # Format float

        respond("📊 *CI/CD Monitoring Summary (via Prometheus):*\n" + "\n".join(results))
    except requests.exceptions.RequestException as e:
        logger.error(f"Prometheus query failed (RequestException): {e}")
        respond(f"❌ Error querying Prometheus: Network or HTTP error. {e}")
    except Exception as e:
        logger.error(f"Error in /monitor-status: {e}", exc_info=True)
        respond(f"❌ An unexpected error occurred querying Prometheus: {e}")


# @app.command("/monitor-pods") # From your provided code
# def handle_monitor_pods(ack, command, respond, logger):
#     ack()
#     logger.info(f"Received /monitor-pods command: {command}")
#     if not PROMETHEUS_URL:
#         respond("Prometheus URL not configured."); return
#     try:
#         query = 'sum(increase(kube_pod_container_status_restarts_total[10m])) by (namespace)' # Example: group by namespace
#         res = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=10)
#         res.raise_for_status()
#         data = res.json().get('data', {}).get('result', [])
        
#         if not data:
#             respond("📈 No pod restart data found in the last 10 minutes.")
#             return

#         results = ["Pod Restarts in last 10 minutes:"]
#         for item in data:
#             namespace = item.get('metric', {}).get('namespace', 'N/A')
#             restarts = int(float(item.get('value', [0, '0'])[1]))
#             results.append(f"  • Namespace `{namespace}`: `{restarts}` restarts")
        
#         respond("\n".join(results))

#     except requests.exceptions.RequestException as e:
#         logger.error(f"Prometheus query failed for /monitor-pods: {e}")
#         respond(f"❌ Error querying Prometheus for pod restarts: Network or HTTP error. {e}")
#     except Exception as e:
#         logger.error(f"Error in /monitor-pods: {e}", exc_info=True)
#         respond(f"❌ An unexpected error occurred: {e}")


@app.command("/grafana-dashboard") # From your provided code
def handle_grafana_dashboard(ack, command, respond, logger):
    ack()
    logger.info(f"Received /grafana-dashboard command: {command}")
    # Consider making this configurable via .env or a config file
    grafana_base_url = os.environ.get("GRAFANA_URL", "http://localhost:3000") # Default if not in .env
    dashboards = {
        "Kubernetes Cluster Overview": f"{grafana_base_url}/d/deldkxqfcvh1cd/kubernetes-cluster-monitoring-via-prometheus?orgId=1&from=now-6h&to=now&timezone=browser", # Example common dashboard
        "Jenkins Overview": f"{grafana_base_url}/d/jenkins-overview/jenkins-overview" # Example
    }
    message = "*📊 Grafana Dashboards:*\n"
    for name, url in dashboards.items():
        message += f"• {name}: <{url}|Open>\n"
    respond(message)

@app.command("/monitor-pods")
def handle_monitor_pods(ack, respond, command):
    ack()
    query = 'kube_pod_status_phase{phase!="Running"}'
    result = query_prometheus(query)
    if isinstance(result, str):  # If error
        respond(result)
    else:
        if not result:
            respond("All pods are running fine.")
        else:
            msg = "Pods not in running state:\n"
            for item in result:
                pod = item['metric'].get('pod', 'Unknown')
                status = item['metric'].get('phase', 'Unknown')
                msg += f"- {pod}: {status}\n"
            respond(msg)

def monitor_loop():
    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    while True:
        alerts = query_prometheus('ALERTS{alertstate="firing"}')
        if alerts:
            for alert in alerts:
                msg = alert['labels'].get('alertname', 'Unknown Alert')
                client.chat_postMessage(channel="#alerts", text=f"🔥 Alert: {msg}")
        time.sleep(300)  # Check every 5 mins

threading.Thread(target=monitor_loop, daemon=True).start()

# --- Remove Flask Setup ---
# flask_app = Flask(__name__) # REMOVE (Corrected from your 'name')
# handler = SlackRequestHandler(app) # REMOVE

# @flask_app.route("/slack/events", methods=["POST"]) # REMOVE
# def slack_events():
#    # Your url_verification and handler.handle(request) logic
#    # This is handled differently by SocketModeHandler
#    return handler.handle(request)


# === Main Execution Block for Socket Mode ===
if __name__ == "__main__":
    # Basic client initialization checks (good to keep)
    if not jenkins_client:
        print("\nWARNING: Jenkins client not initialized. Jenkins commands will fail.\n")
    if not k8s_core_v1_api or not k8s_apps_v1_api:
         print("\nWARNING: Kubernetes client not initialized/config failed. K8s commands will fail.\n")
    if not docker_client:
         print("\nWARNING: Docker client not initialized. Docker commands will fail.\n")
    if not PROMETHEUS_URL:
        print("\nWARNING: PROMETHEUS_URL not set. Prometheus monitoring commands will fail.\n")


    # Start Socket Mode handler
    # Ensure SLACK_APP_TOKEN (xapp-...) is in your .env file
    app_token = os.environ.get("SLACK_APP_TOKEN")
    if not app_token:
        print("ERROR: SLACK_APP_TOKEN not found in environment variables. Socket Mode cannot start.")
    else:
        print("INFO: Starting ChatOps bot in Socket Mode...")
        SocketModeHandler(app, app_token).start()