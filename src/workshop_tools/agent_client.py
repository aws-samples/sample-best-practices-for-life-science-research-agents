"""
Agent client module for communicating with Amazon Bedrock AgentCore.

This module provides the AgentClient class that handles communication with
the Bedrock AgentCore service, including message formatting, session management,
and response handling.
"""

import json
import uuid
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError


class ChatError(Exception):
    """Base exception for chat application errors."""
    pass


class AgentConnectionError(ChatError):
    """Raised when agent connection fails."""
    pass


class ResponseProcessingError(ChatError):
    """Raised when response processing fails."""
    pass


class AgentClient:
    """Client for communicating with Amazon Bedrock AgentCore agents."""
    
    def __init__(self, agent_arn: str, qualifier: str = "DEFAULT"):
        """
        Initialize the AgentClient.
        
        Args:
            agent_arn: The ARN of the Bedrock AgentCore agent
            qualifier: The agent qualifier (default: "DEFAULT")
        """
        self.agent_arn = agent_arn
        self.qualifier = qualifier
        self.client = boto3.client("bedrock-agentcore")
        self.session_id = None
    
    def send_message(self, message: str, session_id: Optional[str] = None) -> Dict:
        """
        Send a message to the agent using InvokeAgentRuntime API.
        
        Args:
            message: The message to send to the agent
            session_id: Optional session ID for conversation continuity
            
        Returns:
            Dict containing the agent response
            
        Raises:
            AgentConnectionError: If the AWS API call fails
            ResponseProcessingError: If response processing fails
        """
        # Use provided session_id or generate/reuse existing one
        if session_id:
            self.session_id = session_id
        elif not self.session_id:
            self.session_id = self._generate_session_id()
        
        # Prepare the payload
        try:
            payload = self._prepare_payload(message)
        except Exception as e:
            raise ResponseProcessingError(f"Failed to prepare message payload: {e}")
        
        # Make the API call (AWS SDK handles retries automatically)
        try:
            response = self.client.invoke_agent_runtime(
                agentRuntimeArn=self.agent_arn,
                qualifier=self.qualifier,
                runtimeSessionId=self.session_id,
                payload=payload
            )
            
            # Format response for ResponseHandler
            content_type = response.get("contentType", "text/event-stream")
            response_body = response.get("response")
            
            # Handle StreamingBody for JSON responses
            if content_type == "application/json" and hasattr(response_body, 'read'):
                response_body = response_body.read().decode('utf-8')
            
            return {
                "contentType": content_type,
                "response": response_body
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            if error_code == 'AccessDeniedException':
                raise AgentConnectionError(f"Access denied: {error_message}")
            elif error_code == 'ResourceNotFoundException':
                raise AgentConnectionError(f"Agent not found: {error_message}")
            elif error_code == 'ThrottlingException':
                raise AgentConnectionError(f"Request throttled: {error_message}")
            elif error_code == 'InternalServerException':
                raise AgentConnectionError(f"Internal server error: {error_message}")
            else:
                raise AgentConnectionError(f"AWS service error ({error_code}): {error_message}")
        
        except Exception as e:
            raise AgentConnectionError(f"Unexpected error communicating with agent: {e}")
    

    
    def _prepare_payload(self, message: str) -> bytes:
        """
        Prepare JSON payload for agent consumption.
        
        Args:
            message: The user message to format
            
        Returns:
            Encoded JSON payload as bytes
        """
        payload = {"prompt": message}
        return json.dumps(payload).encode()
    
    def _generate_session_id(self) -> str:
        """
        Generate unique session ID for conversation continuity.
        
        Returns:
            UUID-based session ID string
        """
        return str(uuid.uuid4())