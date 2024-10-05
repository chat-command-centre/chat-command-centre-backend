#!/usr/bin/env python3
"""Module for azure_ai.py"""

from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential


class AzureAIIntegration:
    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.api_key = api_key
        self.client = TextAnalyticsClient(
            endpoint=endpoint, credential=AzureKeyCredential(api_key)
        )

    def analyze_text(self, documents: list) -> list:
        response = self.client.analyze_sentiment(documents=documents)
        return [doc for doc in response]
