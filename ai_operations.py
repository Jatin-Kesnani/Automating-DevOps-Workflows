import google.generativeai as genai
import os
from typing import Dict, List, Tuple, Optional
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini
GEMINI_API_KEY = "AIzaSyB3B3XUw3gS_Fzw8OVE0hpt6u97xxedd1Q"
genai.configure(api_key=GEMINI_API_KEY)

class AIOpsAssistant:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self.chat = self.model.start_chat(history=[])
        
    def analyze_logs(self, logs: str) -> Dict:
        """Analyze logs and provide insights using AI."""
        try:
            prompt = f"""Analyze these logs and provide:
            1. Error patterns
            2. Performance issues
            3. Security concerns
            4. Recommendations
            
            Logs:
            {logs}
            """
            
            response = self.chat.send_message(prompt)
            return {
                "analysis": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error in log analysis: {str(e)}")
            return {
                "analysis": f"Error analyzing logs: {str(e)}",
                "status": "error"
            }
    
    def suggest_optimization(self, metrics: Dict) -> Dict:
        """Suggest optimizations based on system metrics."""
        try:
            prompt = f"""Based on these system metrics, suggest optimizations:
            1. Resource utilization improvements
            2. Performance tuning recommendations
            3. Cost optimization opportunities
            
            Metrics:
            {json.dumps(metrics, indent=2)}
            """
            
            response = self.chat.send_message(prompt)
            return {
                "suggestions": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error in optimization suggestion: {str(e)}")
            return {
                "suggestions": f"Error generating suggestions: {str(e)}",
                "status": "error"
            }
    
    def predict_anomalies(self, time_series_data: List[Dict]) -> Dict:
        """Predict potential anomalies in time series data."""
        try:
            prompt = f"""Analyze this time series data and predict:
            1. Potential anomalies
            2. Trend analysis
            3. Future predictions
            
            Data:
            {json.dumps(time_series_data, indent=2)}
            """
            
            response = self.chat.send_message(prompt)
            return {
                "predictions": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error in anomaly prediction: {str(e)}")
            return {
                "predictions": f"Error predicting anomalies: {str(e)}",
                "status": "error"
            }
    
    def generate_incident_report(self, incident_data: Dict) -> Dict:
        """Generate a detailed incident report using AI."""
        try:
            prompt = f"""Generate a detailed incident report including:
            1. Root cause analysis
            2. Impact assessment
            3. Resolution steps
            4. Preventive measures
            
            Incident Data:
            {json.dumps(incident_data, indent=2)}
            """
            
            response = self.chat.send_message(prompt)
            return {
                "report": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error generating incident report: {str(e)}")
            return {
                "report": f"Error generating report: {str(e)}",
                "status": "error"
            }
    
    def suggest_workflow_improvements(self, workflow_data: Dict) -> Dict:
        """Suggest improvements for DevOps workflows."""
        try:
            prompt = f"""Analyze this workflow and suggest improvements for:
            1. Automation opportunities
            2. Efficiency gains
            3. Best practices implementation
            4. Risk reduction
            
            Workflow Data:
            {json.dumps(workflow_data, indent=2)}
            """
            
            response = self.chat.send_message(prompt)
            return {
                "improvements": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error suggesting workflow improvements: {str(e)}")
            return {
                "improvements": f"Error generating suggestions: {str(e)}",
                "status": "error"
            } 