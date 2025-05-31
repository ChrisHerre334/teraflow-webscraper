import os
import requests
import json
from typing import Dict, Any
import streamlit as st
from datetime import datetime

class N8NWebhook:
    def __init__(self):
        # Get webhook URL from environment variable
        self.webhook_url = os.getenv('N8N_WEBHOOK_URL')
        if not self.webhook_url:
            st.error("N8N_WEBHOOK_URL environment variable not set!")
    
    def send_data(self, payload: Dict[str, Any]) -> bool:
        """
        Send research data to n8n webhook
        
        Expected payload structure:
        {
            "CompanyName": str,
            "ScrapedContent": str,
            "WhatTheySell": str,
            "WhoTheyTarget": str,
            "CondensedSummary": str,
            "recipientEmail": str
        }
        """
        try:
            if not self.webhook_url:
                print("No webhook URL configured")
                return False
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'AI-Research-Assistant/1.0'
            }
            
            # Add timestamp
            payload['timestamp'] = str(datetime.now())
            
            # Make the POST request
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            # Check if request was successful
            if response.status_code == 200:
                print("Successfully sent data to n8n webhook")
                return True
            else:
                print(f"Webhook request failed with status code: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            print("Webhook request timed out")
            return False
        except requests.exceptions.RequestException as e:
            print(f"Webhook request failed: {str(e)}")
            return False
        except Exception as e:
            print(f"Unexpected error sending webhook: {str(e)}")
            return False
    
    def test_webhook(self) -> bool:
        """Test the webhook connection with sample data"""
        test_payload = {
            "CompanyName": "Test Company",
            "ScrapedContent": "This is test content",
            "WhatTheySell": "Test products and services",
            "WhoTheyTarget": "Test target audience",
            "CondensedSummary": "This is a test summary",
            "recipientEmail": "test@example.com",
            "test": True
        }
        
        return self.send_data(test_payload)