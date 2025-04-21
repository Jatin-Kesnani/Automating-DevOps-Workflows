# jenkins_handler.py
import os
import jenkins
from dotenv import load_dotenv

# Load environment variables (needed if running this file standalone for testing)
load_dotenv()

# --- Jenkins Client Initialization ---
def get_jenkins_client():
    """Initializes and returns a Jenkins client instance."""
    jenkins_url = os.environ.get("JENKINS_URL")
    jenkins_username = os.environ.get("JENKINS_USERNAME")
    jenkins_token = os.environ.get("JENKINS_API_TOKEN")

    if not all([jenkins_url, jenkins_username, jenkins_token]):
        raise ValueError("Jenkins URL, Username, or API Token not found in environment variables.")

    try:
        server = jenkins.Jenkins(jenkins_url, username=jenkins_username, password=jenkins_token)
        # Check connection
        server.get_whoami()
        print("Successfully connected to Jenkins!") # Optional: for verification
        return server
    except jenkins.JenkinsException as e:
        print(f"Error connecting to Jenkins: {e}")
        raise # Re-raise the exception to be handled by the caller

# --- Jenkins Actions ---
def trigger_jenkins_job(server: jenkins.Jenkins, job_name: str):
    """Triggers a build for the specified Jenkins job."""
    try:
        print(f"Attempting to trigger job: {job_name}")
        # Note: build_job might not immediately return queue item details in all configs
        # We primarily care if it raises an exception or not for success/failure of triggering
        server.build_job(job_name)
        print(f"Successfully requested trigger for job: {job_name}")
        # Getting the *exact* build number triggered can be complex immediately
        # For now, we confirm the trigger request was sent without error.
        # We can retrieve the next build number via get_job_info if needed later.
        job_info = server.get_job_info(job_name)
        next_build_number = job_info.get('nextBuildNumber', 'N/A')
        return True, f"Trigger request sent for job `{job_name}`. Next build should be number `{next_build_number}`."

    except jenkins.NotFoundException:
        print(f"Error: Jenkins job '{job_name}' not found.")
        return False, f"Error: Jenkins job `{job_name}` not found."
    except jenkins.JenkinsException as e:
        print(f"Error triggering Jenkins job '{job_name}': {e}")
        return False, f"Error triggering job `{job_name}`: {e}"
    except Exception as e: # Catch other potential errors
        print(f"An unexpected error occurred during trigger: {e}")
        return False, f"An unexpected error occurred while triggering `{job_name}`."

def get_job_status(server: jenkins.Jenkins, job_name: str):
    """Gets the status information of the last completed build for a job."""
    try:
        print(f"Attempting to get status for job: {job_name}")
        job_info = server.get_job_info(job_name)
        last_build_number = job_info.get('lastCompletedBuild', {}).get('number') if job_info.get('lastCompletedBuild') else None

        if last_build_number is None:
             # Check if there's a build currently running
             last_build = job_info.get('lastBuild', {}).get('number') if job_info.get('lastBuild') else None
             if last_build:
                 try:
                     build_info = server.get_build_info(job_name, last_build)
                     if build_info.get('building'):
                         duration_ms = build_info.get('estimatedDuration', 0)
                         duration_s = duration_ms // 1000
                         return True, f"Job `{job_name}` build `#{last_build}` is currently RUNNING (estimated duration: {duration_s}s)."
                 except jenkins.NotFoundException:
                     # Build might have just finished or disappeared, fallback
                     pass
             return True, f"Job `{job_name}` found, but no completed builds yet (or last build is running)."


        build_info = server.get_build_info(job_name, last_build_number)

        status = build_info.get('result', 'UNKNOWN') # SUCCESS, FAILURE, ABORTED, UNSTABLE
        duration_ms = build_info.get('duration', 0)
        duration_s = duration_ms // 1000 # Jenkins duration is in ms
        build_url = build_info.get('url', '#')

        return True, f"Status for `{job_name}` (Build `#{last_build_number}`): `{status}` (Duration: {duration_s}s)\n<{build_url}|View Build>"

    except jenkins.NotFoundException:
        print(f"Error: Jenkins job '{job_name}' not found.")
        return False, f"Error: Jenkins job `{job_name}` not found."
    except jenkins.JenkinsException as e:
        print(f"Error getting Jenkins job status for '{job_name}': {e}")
        return False, f"Error getting status for `{job_name}`: {e}"
    except Exception as e:
        print(f"An unexpected error occurred during status check: {e}")
        return False, f"An unexpected error occurred while checking status for `{job_name}`."

# Example of how to test functions directly (optional)
if __name__ == "__main__":
    try:
        client = get_jenkins_client()
        if client:
             # --- Test Trigger ---
             # Make sure 'SampleJob' exists in your Jenkins
             # test_job = "SampleJob"
             # success, message = trigger_jenkins_job(client, test_job)
             # print(f"Trigger Test: Success={success}, Message={message}")

             # --- Test Status ---
             # Make sure 'SampleJob' has run at least once
             test_job_status = "SampleJob"
             success_status, message_status = get_job_status(client, test_job_status)
             print(f"Status Test: Success={success_status}, Message={message_status}")

             # --- Test Non-Existent Job ---
             # non_existent_job = "JobThatDoesNotExist"
             # success_ne, message_ne = get_job_status(client, non_existent_job)
             # print(f"Non-Existent Test: Success={success_ne}, Message={message_ne}")

    except ValueError as e:
        print(e)
    except Exception as e:
        print(f"An error occurred during direct testing: {e}")