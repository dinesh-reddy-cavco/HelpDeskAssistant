"""Azure AI Foundry service for chat completions."""
import os
from openai import AzureOpenAI
from app.config import settings
from typing import List, Dict, Optional


class AzureOpenAIService:
    """Service for interacting with Azure AI Foundry."""
    
    def __init__(self):
        """Initialize Azure AI Foundry client."""
        # Ensure endpoint ends with / for proper URL construction
        endpoint = settings.azure_foundry_endpoint
        if not endpoint.endswith('/'):
            endpoint = endpoint + '/'
        
        self.client = AzureOpenAI(
            api_key=settings.azure_foundry_api_key,
            api_version=settings.azure_foundry_api_version,
            azure_endpoint=endpoint
        )
        self.deployment_name = settings.azure_foundry_deployment_name
        
        # System prompt for Phase 1 - Safe, conservative behavior
        self.system_prompt = """You are a helpful IT support assistant for Cavco Industries. 
Your role is to assist users with common IT issues while being safe and conservative.

Guidelines:
1. Answer common IT questions clearly and helpfully (passwords, VPN, printers, common apps)
2. If you're not confident about an answer, say so and suggest creating a ticket
3. Be professional and friendly
4. Focus on common, generic IT support questions
5. If the question is too specific or you're unsure, recommend escalation

For Phase 1, you should:
- Answer generic IT questions confidently
- Refuse to guess on complex or unclear issues
- Always suggest ticket creation when uncertain

Remember: It's better to escalate than to give incorrect information."""
    
    def get_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """
        Get chat completion from Azure OpenAI.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Assistant's response text
        """
        try:
            # Prepare messages with system prompt
            formatted_messages = [
                {"role": "system", "content": self.system_prompt}
            ] + messages
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise Exception(f"Error calling Azure OpenAI: {str(e)}")
    
    def format_messages_for_api(self, history: List[Dict]) -> List[Dict[str, str]]:
        """
        Format conversation history for OpenAI API.
        
        Args:
            history: List of message dictionaries
            
        Returns:
            Formatted messages list
        """
        formatted = []
        for msg in history:
            formatted.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        return formatted
