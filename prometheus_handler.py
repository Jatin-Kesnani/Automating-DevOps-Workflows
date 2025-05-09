# prometheus_handler.py
import requests
import os

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL")

def query_prometheus(query):
    try:
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
        response.raise_for_status()
        data = response.json()
        return data['data']['result']
    except Exception as e:
        return f"Error querying Prometheus: {str(e)}"
