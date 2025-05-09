# jenkins_handler.py
import os
import jenkins
from dotenv import load_dotenv
import logging # Import the logging module

# Load environment variables
load_dotenv()

# Setup a logger for this module
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# --- Jenkins Client Initialization ---
def get_jenkins_client():
    """Initializes and returns a Jenkins client instance."""
    jenkins_url = os.environ.get("JENKINS_URL")
    jenkins_username = os.environ.get("JENKINS_USERNAME")
    jenkins_token = os.environ.get("JENKINS_API_TOKEN")

    if not all([jenkins_url, jenkins_username, jenkins_token]):
        logger.error("Jenkins URL, Username, or API Token not found in environment variables.")
        raise ValueError("Jenkins URL, Username, or API Token not found in environment variables.")

    try:
        server = jenkins.Jenkins(jenkins_url, username=jenkins_username, password='admin')
        server.get_whoami() # Check connection
        logger.info("Successfully connected to Jenkins!")
        return server
    except jenkins.JenkinsException as e:
        logger.error(f"Error connecting to Jenkins: {e}")
        raise # Re-raise the exception to be handled by the caller
    except Exception as e:
        logger.error(f"An unexpected error occurred during Jenkins client initialization: {e}")
        raise


# --- Jenkins Actions ---
def trigger_jenkins_job(server: jenkins.Jenkins, job_name: str, params: dict = None):
    """
    Triggers a build for the specified Jenkins job, optionally with parameters.
    params should be a dictionary like {'PARAM_NAME': 'value'}
    """
    try:
        logger.info(f"Attempting to trigger job: '{job_name}' with params: {params}")
        server.build_job(job_name, parameters=params)
        logger.info(f"Successfully requested trigger for job: '{job_name}'")

        job_info = server.get_job_info(job_name)
        next_build_number = job_info.get('nextBuildNumber', 'N/A')
        param_info = f" with parameters `{params}`" if params else ""
        return True, f"Trigger request sent for job `{job_name}`{param_info}. Next build should be number `{next_build_number}`."

    except jenkins.NotFoundException:
        logger.error(f"Jenkins job '{job_name}' not found during trigger.")
        return False, f"Error: Jenkins job `{job_name}` not found."
    except jenkins.JenkinsException as e:
        logger.error(f"JenkinsException triggering job '{job_name}': {e}")
        param_info = f" with parameters `{params}`" if params else ""
        return False, f"Error triggering job `{job_name}`{param_info}: {e}"
    except Exception as e:
        logger.error(f"Unexpected error triggering job '{job_name}': {e}", exc_info=True)
        param_info = f" with parameters `{params}`" if params else ""
        return False, f"An unexpected error occurred while triggering `{job_name}`{param_info}."


def get_job_status(server: jenkins.Jenkins, job_name: str):
    """Gets the status information of the last completed or current build for a job."""
    try:
        logger.info(f"Attempting to get status for job: '{job_name}'")
        job_info = server.get_job_info(job_name)

        # Prioritize lastBuild if it's currently building
        last_build_number_info = job_info.get('lastBuild')
        if last_build_number_info:
            current_build_number = last_build_number_info.get('number')
            if current_build_number is not None:
                try:
                    build_info = server.get_build_info(job_name, current_build_number)
                    if build_info.get('building'):
                        duration_ms = build_info.get('estimatedDuration', 0)
                        duration_s = duration_ms // 1000
                        build_url = build_info.get('url', '#')
                        return True, f"Job `{job_name}` build `#{current_build_number}` is currently RUNNING (Est. duration: {duration_s}s)\n<{build_url}|View Build>"
                except jenkins.NotFoundException:
                    logger.warning(f"Build #{current_build_number} for job '{job_name}' not found while checking if running.")
                    pass # Fall through to check lastCompletedBuild

        # If not building, or lastBuild info was problematic, check lastCompletedBuild
        last_completed_build_info = job_info.get('lastCompletedBuild')
        if last_completed_build_info and last_completed_build_info.get('number') is not None:
            last_build_number = last_completed_build_info.get('number')
            build_info = server.get_build_info(job_name, last_build_number)
            status = build_info.get('result', 'UNKNOWN')
            duration_ms = build_info.get('duration', 0)
            duration_s = duration_ms // 1000
            build_url = build_info.get('url', '#')
            return True, f"Status for `{job_name}` (Build `#{last_build_number}`): `{status}` (Duration: {duration_s}s)\n<{build_url}|View Build>"
        
        # If no completed build and no currently running build found clearly
        if last_build_number_info and last_build_number_info.get('number') is not None: # There is a last build, but it wasn't running and not 'lastCompleted'
             return True, f"Job `{job_name}` (Build `#{last_build_number_info.get('number')}`) status is not 'RUNNING' and it's not the last *completed* build. It might be queued or in a post-build state."

        return True, f"Job `{job_name}` found, but no build information (running or completed) could be retrieved."

    except jenkins.NotFoundException:
        logger.error(f"Jenkins job '{job_name}' not found during status check.")
        return False, f"Error: Jenkins job `{job_name}` not found."
    except jenkins.JenkinsException as e:
        logger.error(f"JenkinsException getting status for job '{job_name}': {e}")
        return False, f"Error getting status for `{job_name}`: {e}"
    except Exception as e:
        logger.error(f"Unexpected error getting status for job '{job_name}': {e}", exc_info=True)
        return False, f"An unexpected error occurred while checking status for `{job_name}`."


def get_build_log(server: jenkins.Jenkins, job_name: str, build_number_str: str = 'lastBuild'):
    """Gets console output log for a specific Jenkins build."""
    try:
        logger.info(f"Attempting to get log for job '{job_name}', build '{build_number_str}'")

        resolved_build_number = None
        if build_number_str.lower() == 'lastbuild':
            job_info = server.get_job_info(job_name)
            # Try various keys for the 'last' build concept
            for build_key in ['lastBuild', 'lastCompletedBuild', 'lastSuccessfulBuild', 'lastFailedBuild']:
                if job_info.get(build_key) and job_info[build_key].get('number') is not None:
                    resolved_build_number = job_info[build_key]['number']
                    break
            if resolved_build_number is None:
                 return False, f"Could not determine any recent build number for job `{job_name}`. Has it run?"
            logger.info(f"Resolved 'lastBuild' for '{job_name}' to build number {resolved_build_number}")
        else:
            try:
                resolved_build_number = int(build_number_str)
            except ValueError:
                return False, f"Invalid build number specified: `{build_number_str}`. Please use a number or 'lastBuild'."

        log_output = server.get_build_console_output(job_name, resolved_build_number)

        if not log_output: # Log might be empty if build is very new or has no output
             try:
                build_info = server.get_build_info(job_name, resolved_build_number)
                if build_info.get('building'):
                    return True, f"Build `#{resolved_build_number}` for job `{job_name}` is still RUNNING. Log is not yet complete or available."
                else: # Build exists, not running, but log is empty
                    return True, f"Build `#{resolved_build_number}` for job `{job_name}` found, but its log output is empty."
             except jenkins.NotFoundException: # Build number itself not found
                 return False, f"Build `#{resolved_build_number}` not found for job `{job_name}`."

        max_chars = 3500  # Leave some buffer for Slack message limits
        truncated_info = ""
        if len(log_output) > max_chars:
            log_output_display = log_output[-max_chars:]  # Get the *end* of the log
            truncated_info = f"... (Log truncated to last {max_chars} characters) ...\n"
        else:
            log_output_display = log_output
        
        message = f"Console Log for `{job_name}` Build `#{resolved_build_number}`:\n{truncated_info}```\n{log_output_display}\n```"
        return True, message

    except jenkins.NotFoundException:
        logger.warning(f"NotFoundException for job '{job_name}' or build '{build_number_str}'.")
        try: # Check if job exists at all
            server.get_job_info(job_name) # If this passes, the job exists but build_number_str was bad
            return False, f"Build specified as `'{build_number_str}'` (resolved to `#{resolved_build_number}` if applicable) not found for job `{job_name}`."
        except jenkins.NotFoundException: # Job itself does not exist
            return False, f"Job `{job_name}` not found."
    except jenkins.JenkinsException as e:
        logger.error(f"JenkinsException getting log for '{job_name}' build '{build_number_str}': {e}")
        return False, f"Error getting logs for job `{job_name}` build `{build_number_str}`: {e}"
    except Exception as e:
        logger.error(f"Unexpected error getting logs for '{job_name}' build '{build_number_str}': {e}", exc_info=True)
        return False, f"An unexpected error occurred while getting logs for `{job_name}` build `{build_number_str}`."


# Example of how to test functions directly (optional)
if __name__ == "__main__": # Corrected from 'name'
    logger.info("Attempting direct test of jenkins_handler functions...")
    try:
        client = get_jenkins_client()
        if client:
            test_job = "SampleJob" # Replace with a job that exists in your Jenkins
            param_job = "ParamJob"  # Replace with a parameterized job

            logger.info(f"\n--- Testing Trigger ({test_job}) ---")
            # success_trigger, msg_trigger = trigger_jenkins_job(client, test_job)
            # logger.info(f"Trigger Test: Success={success_trigger}, Message={msg_trigger}")

            logger.info(f"\n--- Testing Trigger ({param_job} with params) ---")
            # params_to_send = {"ENV": "test-direct", "VERSION": "0.0.handler"}
            # success_trigger_param, msg_trigger_param = trigger_jenkins_job(client, param_job, params=params_to_send)
            # logger.info(f"Param Trigger Test: Success={success_trigger_param}, Message={msg_trigger_param}")

            logger.info(f"\n--- Testing Status ({test_job}) ---")
            # Make sure test_job has run at least once
            success_status, msg_status = get_job_status(client, test_job)
            logger.info(f"Status Test: Success={success_status}, Message={msg_status}")

            logger.info(f"\n--- Testing Log ({test_job}, lastBuild) ---")
            # success_log_last, msg_log_last = get_build_log(client, test_job)
            # logger.info(f"Log (lastBuild) Test: Success={success_log_last}\n{msg_log_last[:500]}...") # Print first 500 chars of log

            logger.info(f"\n--- Testing Log ({test_job}, build #1) ---")
            # Check if build #1 exists for test_job
            # success_log_1, msg_log_1 = get_build_log(client, test_job, "1")
            # logger.info(f"Log (build 1) Test: Success={success_log_1}\n{msg_log_1[:500]}...")

            logger.info(f"\n--- Testing Non-Existent Job ---")
            # success_ne, msg_ne = get_job_status(client, "JobThatDoesNotExist")
            # logger.info(f"Non-Existent Test: Success={success_ne}, Message={msg_ne}")
        else:
            logger.error("Failed to get Jenkins client for direct testing.")

    except ValueError as e: # From get_jenkins_client if env vars are missing
        logger.error(f"Configuration Error: {e}")
    except Exception as e:
        logger.error(f"An error occurred during direct testing of jenkins_handler: {e}", exc_info=True)