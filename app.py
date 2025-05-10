import os
import docker
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import jenkins_handler
import jenkins
import k8s_handler
from kubernetes import client
import docker_handler
from docker.errors import DockerException
import requests

import threading
import time
from slack_sdk import WebClient

# Import new modules
from ai_operations import AIOpsAssistant
from advanced_monitoring import AdvancedMonitoring

# Import the WebsiteHandler
from website_handler import WebsiteHandler

# Load environment variables from .env file
load_dotenv()

# Initialize Slack Bolt app
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Initialize AI and Monitoring
ai_assistant = AIOpsAssistant()
advanced_monitor = AdvancedMonitoring()

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

# Initialize WebsiteHandler
website_handler = WebsiteHandler(docker_client)

# === Event Handlers (like app_mention) and Command Handlers remain THE SAME ===
# Your @app.event("app_mention") and all @app.command(...) handlers
# do not need to change for Socket Mode.

@app.event("app_mention")
def handle_app_mention_events(body, say, logger):
    logger.info("Received app_mention event")
    message_text = body["event"]["text"]
    user_id = body["event"]["user"]
    
    # Check if the message is requesting command list
    if "ls-commands" in message_text.lower():
        # Define command categories and their commands
        commands = {
            "🤖 AI-Powered Commands": [
                "/ai-analyze-logs <source> - Analyze logs from Jenkins, K8s, or Docker",
                "/ai-optimize - Get AI-powered system optimization suggestions",
                "/system-health - Get comprehensive system health score",
                "/detect-anomalies <metric> [duration] - Detect anomalies in metrics",
                "/capacity-planning - Get capacity planning insights"
            ],
            "🔄 CI/CD Commands": [
                "/jenkins-trigger <job_name> [params] - Trigger Jenkins jobs",
                "/jenkins-status <job_name> - Check Jenkins job status",
                "/jenkins-log <job_name> [build_number] - Get Jenkins build logs",
                "/jenkins-deploy <job_name> - Deploy application using Jenkins"
            ],
            "🐳 Docker Commands": [
                "/docker-ps - List running Docker containers",
                "/docker-logs <container_name> - Get container logs",
                "/docker-deploy <image_name> - Deploy container using Docker"
            ],
            "☸️ Kubernetes Commands": [
                "/k8s-pods [namespace] - List Kubernetes pods",
                "/k8s-deployments [namespace] - List Kubernetes deployments",
                "/k8s-restart-deployment <deployment-name> [namespace] - Restart a deployment"
            ],
            "📊 Monitoring Commands": [
                "/monitor-status - Get CI/CD monitoring summary",
                "/monitor-pods - Check pod status",
                "/grafana-dashboard - Access Grafana dashboards"
            ]
        }
        
        # Build the response message
        response = "📋 *Available ChatOps Commands:*\n\n"
        for category, cmd_list in commands.items():
            response += f"*{category}*\n"
            for cmd in cmd_list:
                response += f"• `{cmd}`\n"
            response += "\n"
        
        response += "💡 *Tip:* Use `/help <command>` for detailed information about a specific command."
        say(response)
    else:
        # Default response for other mentions
        response_text = f"Hi <@{user_id}>! You mentioned me. You said: '{message_text}'\n\nUse `@chatops ls-commands` to see all available commands."
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


@app.command("/monitor-status")
def handle_monitor_status(ack, command, respond, logger):
    ack()
    logger.info(f"Received /monitor-status command: {command}")
    respond("Monitoring functionality has been removed from this version of the bot.")

@app.command("/monitor-pods")
def handle_monitor_pods(ack, respond, command):
    ack()
    respond("Monitoring functionality has been removed from this version of the bot.")

@app.command("/grafana-dashboard")
def handle_grafana_dashboard(ack, command, respond, logger):
    ack()
    logger.info(f"Received /grafana-dashboard command: {command}")
    respond("Monitoring functionality has been removed from this version of the bot.")

# New command handlers for AI and advanced monitoring features
@app.command("/ai-analyze-logs")
def handle_ai_analyze_logs(ack, body, command, respond, logger):
    ack()
    logger.info(f"Received /ai-analyze-logs command: {command}")
    
    # Get logs from the specified source
    source = command.get('text', '').strip()
    if not source:
        respond("Please specify the log source (e.g., 'jenkins', 'k8s', 'docker')")
        return
    
    try:
        logs = ""
        if source == "jenkins":
            success, logs = jenkins_handler.get_recent_logs(jenkins_client)
        elif source == "k8s":
            success, logs = k8s_handler.get_recent_logs(k8s_core_v1_api)
        elif source == "docker":
            success, logs = docker_handler.get_recent_logs(docker_client)
        else:
            respond(f"Unsupported log source: {source}")
            return
        
        if not success:
            respond(f"Failed to fetch logs from {source}")
            return
        
        # Analyze logs using AI
        result = ai_assistant.analyze_logs(logs)
        if result["status"] == "success":
            respond(f"🤖 *AI Analysis of {source} logs:*\n{result['analysis']}")
        else:
            respond(f"❌ Error analyzing logs: {result['analysis']}")
    except Exception as e:
        logger.error(f"Error in AI log analysis: {str(e)}")
        respond(f"❌ An error occurred: {str(e)}")

@app.command("/system-health")
def handle_system_health(ack, body, command, respond, logger):
    ack()
    logger.info(f"Received /system-health command: {command}")
    
    try:
        health_data = advanced_monitor.get_system_health_score()
        if health_data["status"] == "success":
            metrics = health_data["metrics"]
            health_score = health_data["health_score"]
            
            # Format the response
            response = f"🏥 *System Health Score: {health_score:.1f}%*\n\n"
            response += "*Detailed Metrics:*\n"
            for metric, value in metrics.items():
                response += f"• {metric.replace('_', ' ').title()}: {value:.1f}\n"
            
            respond(response)
        else:
            respond(f"❌ Error getting system health: {health_data['message']}")
    except Exception as e:
        logger.error(f"Error in system health check: {str(e)}")
        respond(f"❌ An error occurred: {str(e)}")

@app.command("/detect-anomalies")
def handle_detect_anomalies(ack, body, command, respond, logger):
    ack()
    logger.info(f"Received /detect-anomalies command: {command}")
    
    args = command.get('text', '').strip().split()
    if len(args) < 1:
        respond("Usage: /detect-anomalies <metric_name> [duration]")
        return
    
    metric_name = args[0]
    duration = args[1] if len(args) > 1 else "1h"
    
    try:
        result = advanced_monitor.detect_anomalies(metric_name, duration)
        if result["status"] == "success":
            anomalies = result["anomalies"]
            stats = result["statistics"]
            
            response = f"🔍 *Anomaly Detection for {metric_name}*\n\n"
            response += f"*Statistics:*\n"
            response += f"• Mean: {stats['mean']:.2f}\n"
            response += f"• Std Dev: {stats['std']:.2f}\n"
            response += f"• Min: {stats['min']:.2f}\n"
            response += f"• Max: {stats['max']:.2f}\n\n"
            
            if anomalies:
                response += f"*Detected Anomalies:*\n"
                for anomaly in anomalies[:5]:  # Show top 5 anomalies
                    response += f"• Time: {anomaly['timestamp']}, Value: {anomaly['value']:.2f}\n"
                if len(anomalies) > 5:
                    response += f"... and {len(anomalies) - 5} more anomalies"
            else:
                response += "No anomalies detected in the specified time range."
            
            respond(response)
        else:
            respond(f"❌ Error detecting anomalies: {result['message']}")
    except Exception as e:
        logger.error(f"Error in anomaly detection: {str(e)}")
        respond(f"❌ An error occurred: {str(e)}")

@app.command("/capacity-planning")
def handle_capacity_planning(ack, body, command, respond, logger):
    ack()
    logger.info(f"Received /capacity-planning command: {command}")
    
    try:
        insights = advanced_monitor.get_capacity_planning_insights()
        if insights["status"] == "success":
            response = "📊 *Capacity Planning Insights*\n\n"
            
            for resource, data in insights["insights"].items():
                response += f"*{resource.upper()}*\n"
                response += f"• Current Usage: {data['current_usage']:.2f}\n"
                response += f"• Growth Rate: {data['growth_rate']:.1f}%\n"
                response += f"• Predicted Usage: {data['predicted_usage']:.2f}\n"
                response += f"• Recommendation: {data['recommendation']}\n\n"
            
            respond(response)
        else:
            respond(f"❌ Error getting capacity insights: {insights['message']}")
    except Exception as e:
        logger.error(f"Error in capacity planning: {str(e)}")
        respond(f"❌ An error occurred: {str(e)}")

@app.command("/ai-optimize")
def handle_ai_optimize(ack, body, command, respond, logger):
    ack()
    logger.info(f"Received /ai-optimize command: {command}")
    
    try:
        # Get current system metrics
        health_data = advanced_monitor.get_system_health_score()
        if health_data["status"] != "success":
            respond(f"❌ Error getting system metrics: {health_data['message']}")
            return
        
        # Get optimization suggestions from AI
        result = ai_assistant.suggest_optimization(health_data["metrics"])
        if result["status"] == "success":
            respond(f"🤖 *AI Optimization Suggestions:*\n{result['suggestions']}")
        else:
            respond(f"❌ Error getting optimization suggestions: {result['suggestions']}")
    except Exception as e:
        logger.error(f"Error in AI optimization: {str(e)}")
        respond(f"❌ An error occurred: {str(e)}")

# Add a help command handler
@app.command("/help")
def handle_help_command(ack, body, command, respond, logger):
    ack()
    logger.info(f"Received /help command: {command}")
    
    # Get the specific command to get help for
    cmd = command.get('text', '').strip()
    
    # Define detailed help information for each command
    help_info = {
        "ai-analyze-logs": {
            "description": "Analyze logs using AI to identify patterns and issues",
            "usage": "/ai-analyze-logs <source>",
            "examples": [
                "/ai-analyze-logs jenkins",
                "/ai-analyze-logs k8s",
                "/ai-analyze-logs docker"
            ],
            "notes": "The AI will analyze logs for error patterns, performance issues, and security concerns."
        },
        "jenkins-trigger": {
            "description": "Trigger a Jenkins job with optional parameters",
            "usage": "/jenkins-trigger <job_name> [param1=value1 param2=value2 ...]",
            "examples": [
                "/jenkins-trigger build-app",
                "/jenkins-trigger deploy-app environment=prod version=1.0.0"
            ],
            "notes": "Parameters should be in key=value format, separated by spaces."
        },
        "jenkins-deploy": {
            "description": "Deploy an application using Jenkins pipeline",
            "usage": "/jenkins-deploy <job_name>",
            "examples": [
                "/jenkins-deploy website-deploy",
                "/jenkins-deploy app-deploy"
            ],
            "notes": "This will trigger the specified Jenkins deployment job."
        },
        "docker-ps": {
            "description": "List all running Docker containers",
            "usage": "/docker-ps",
            "examples": [
                "/docker-ps"
            ],
            "notes": "Shows container ID, image, status, and names."
        },
        "docker-deploy": {
            "description": "Deploy a Docker container",
            "usage": "/docker-deploy <image_name>",
            "examples": [
                "/docker-deploy website",
                "/docker-deploy app"
            ],
            "notes": "This will deploy the specified Docker image."
        },
        "k8s-pods": {
            "description": "List pods in a Kubernetes namespace",
            "usage": "/k8s-pods [namespace]",
            "examples": [
                "/k8s-pods",
                "/k8s-pods production"
            ],
            "notes": "If namespace is not specified, defaults to 'default'."
        }
    }
    
    if not cmd:
        # If no specific command is requested, show general help
        respond("Please specify a command to get help for. Usage: `/help <command>`\n\nAvailable commands:\n" + 
                "\n".join([f"• `{cmd}`" for cmd in help_info.keys()]))
        return
    
    # Get help for specific command
    if cmd in help_info:
        info = help_info[cmd]
        response = f"*Help for `{cmd}`*\n\n"
        response += f"*Description:* {info['description']}\n"
        response += f"*Usage:* `{info['usage']}`\n"
        response += "*Examples:*\n" + "\n".join([f"• `{ex}`" for ex in info['examples']]) + "\n"
        response += f"*Notes:* {info['notes']}"
        respond(response)
    else:
        respond(f"Sorry, I don't have help information for the command `{cmd}`.\n\nAvailable commands:\n" + 
                "\n".join([f"• `{cmd}`" for cmd in help_info.keys()]))

@app.command("/docker-deploy")
def handle_docker_deploy_command(ack, body, command, respond, logger):
    ack()
    logger.info(f"Received /docker-deploy command: {command}")
    
    image_name = command.get('text', '').strip()
    if not image_name:
        respond("Please provide the image name. Usage: `/docker-deploy <image_name>`")
        return
    
    if not docker_client:
        respond("Sorry, Docker connection failed. Check logs.")
        return
    
    try:
        # Pull the image if it doesn't exist locally
        try:
            docker_client.images.get(image_name)
        except docker.errors.ImageNotFound:
            logger.info(f"Image {image_name} not found locally, pulling...")
            docker_client.images.pull(image_name)
        
        # Stop and remove existing container if it exists
        container_name = f"{image_name}-container"
        try:
            existing_container = docker_client.containers.get(container_name)
            logger.info(f"Stopping and removing existing container: {container_name}")
            existing_container.stop()
            existing_container.remove()
        except docker.errors.NotFound:
            pass  # Container doesn't exist, which is fine
        
        # Run the container
        container = docker_client.containers.run(
            image_name,
            detach=True,
            ports={'80/tcp': 80},  # Map container port 80 to host port 80
            name=container_name
        )
        
        respond(f"✅ Successfully deployed {image_name} container. Container ID: {container.id}")
    except Exception as e:
        logger.error(f"Error deploying Docker container: {str(e)}")
        respond(f"❌ Error deploying container: {str(e)}")

@app.command("/jenkins-deploy")
def handle_jenkins_deploy_command(ack, body, command, respond, logger):
    ack()
    logger.info(f"Received /jenkins-deploy command: {command}")
    
    job_name = command.get('text', '').strip()
    if not job_name:
        respond("Please provide the Jenkins job name. Usage: `/jenkins-deploy <job_name>`")
        return
    
    if not jenkins_client:
        respond("Sorry, Jenkins connection failed. Check logs.")
        return
    
    try:
        # Trigger the deployment job
        success, message = jenkins_handler.trigger_jenkins_job(jenkins_client, job_name)
        if success:
            respond(f"✅ Successfully triggered deployment job: {job_name}\n{message}")
        else:
            respond(f"❌ Failed to trigger deployment job: {message}")
    except Exception as e:
        logger.error(f"Error triggering Jenkins deployment job: {str(e)}")
        respond(f"❌ Error: {str(e)}")

@app.command("/deploy-website")
def handle_deploy_website(ack, body, command, respond, logger):
    ack()
    logger.info(f"Received /deploy-website command: {command}")
    
    try:
        # Get website name from command text, default to "my-website" if not provided
        website_name = command.get('text', '').strip() or "my-website"
        
        # Deploy the website
        success, message = website_handler.deploy_website(website_name)
        
        if success:
            respond(message)
        else:
            respond(f"❌ {message}")
            
    except Exception as e:
        logger.error(f"Error in deploy-website command: {str(e)}", exc_info=True)
        respond(f"❌ An error occurred while deploying the website: {str(e)}")

# === Main Execution Block for Socket Mode ===
if __name__ == "__main__":
    # Basic client initialization checks (good to keep)
    if not jenkins_client:
        print("\nWARNING: Jenkins client not initialized. Jenkins commands will fail.\n")
    if not k8s_core_v1_api or not k8s_apps_v1_api:
         print("\nWARNING: Kubernetes client not initialized/config failed. K8s commands will fail.\n")
    if not docker_client:
         print("\nWARNING: Docker client not initialized. Docker commands will fail.\n")

    # Start Socket Mode handler
    # Ensure SLACK_APP_TOKEN (xapp-...) is in your .env file
    app_token = os.environ.get("SLACK_APP_TOKEN")
    if not app_token:
        print("ERROR: SLACK_APP_TOKEN not found in environment variables. Socket Mode cannot start.")
    else:
        print("INFO: Starting ChatOps bot in Socket Mode...")
        handler = SocketModeHandler(app, app_token)
        handler.start()