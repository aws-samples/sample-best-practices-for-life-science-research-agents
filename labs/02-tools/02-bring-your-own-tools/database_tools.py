# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import logging
import os
import re
import boto3
import requests
from typing import Any, Dict, List, Literal
from utils import get_ssm_parameter
from strands.tools.mcp import MCPClient, MCPAgentTool
from mcp.types import Tool as MCPTool
from mcp.client.streamable_http import streamablehttp_client

# Global configuration for commercial use filtering
COMMERCIAL_USE_ONLY = os.getenv("COMMERCIAL_USE_ONLY", True)

# Configure logging
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger("search_database_tools")
logger.setLevel(logging.INFO)

def get_gateway_access_token():
    """Get M2M bearer token for gateway authentication."""
    try:
        # Get credentials from SSM
        machine_client_id = get_ssm_parameter("/deep-research-workshop/agentcore/machine_client_id")
        machine_client_secret = get_ssm_parameter("/deep-research-workshop/agentcore/cognito_secret")
        cognito_domain = get_ssm_parameter("/deep-research-workshop/agentcore/cognito_domain")
        user_pool_id = get_ssm_parameter("/deep-research-workshop/agentcore/userpool_id")

        # Clean the domain
        cognito_domain = cognito_domain.strip()
        if cognito_domain.startswith("https://"):
            cognito_domain = cognito_domain[8:]

        # Get resource server scopes
        cognito_client = boto3.client('cognito-idp')
        response = cognito_client.list_resource_servers(UserPoolId=user_pool_id, MaxResults=1)
        
        if response['ResourceServers']:
            resource_server_id = response['ResourceServers'][0]['Identifier']
            scopes = f"{resource_server_id}/read"
        else:
            scopes = "gateway:read gateway:write"

        # M2M OAuth flow
        token_url = f"https://{cognito_domain}/oauth2/token"
        token_data = {
            "grant_type": "client_credentials",
            "client_id": machine_client_id,
            "client_secret": machine_client_secret,
            "scope": scopes
        }
        
        response = requests.post(
            token_url, 
            data=token_data, 
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"Failed to get access token: {response.text}")
            return None
            
        access_token = response.json()["access_token"]
        return access_token
        
    except Exception as e:
        print(f"Error getting M2M bearer token: {str(e)}")
        return None

def get_all_mcp_tools_from_mcp_client(client):
    """Get all tools from MCP client with pagination."""
    more_tools = True
    tools = []
    pagination_token = None
    while more_tools:
        tmp_tools = client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(tmp_tools)
        if tmp_tools.pagination_token is None:
            more_tools = False
        else:
            more_tools = True
            pagination_token = tmp_tools.pagination_token
    return tools

def tool_search(gateway_endpoint, jwt_token, query, max_tools=5):
    """Search for tools using the gateway's semantic search."""
    tool_params = {
        "name": "x_amz_bedrock_agentcore_search",
        "arguments": {"query": query},
    }
    
    request_body = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": tool_params,
    }
    
    response = requests.post(
        gateway_endpoint,
        json=request_body,
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        },
        timeout=30
    )
    
    if response.status_code == 200:
        tool_resp = response.json()
        tools = _extract_tools_from_result(tool_resp.get("result", {}))
        tools = tools[:max_tools]
        return tools
    else:
        print(f"Search failed: {response.text}")
        return []


def _extract_tools_from_result(result):
    """Extract the tool list from an MCP tools/call result.

    The Bedrock AgentCore Gateway used to return the tools under
    ``result["structuredContent"]["tools"]``. Newer responses omit
    ``structuredContent`` and instead return a ``content`` array of blocks,
    each with a ``type`` and ``text`` (the text being JSON). Handle both.
    """
    # Preferred (legacy) shape: structuredContent.tools
    structured = result.get("structuredContent")
    if isinstance(structured, dict) and "tools" in structured:
        return structured["tools"]

    # Fallback: parse the content blocks, whose text holds JSON
    tools = []
    for block in result.get("content", []):
        if block.get("type") != "text":
            continue
        text = block.get("text", "")
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict) and "tools" in parsed:
            tools.extend(parsed["tools"])
        elif isinstance(parsed, list):
            tools.extend(parsed)
        elif isinstance(parsed, dict) and "name" in parsed:
            tools.append(parsed)
    return tools
    
def tools_to_strands_mcp_tools(tools, top_n, client):
    """Convert search results to Strands MCPAgentTool objects."""
    strands_mcp_tools = []
    for tool in tools[:top_n]:
        mcp_tool = MCPTool(
            name=tool["name"],
            description=tool["description"],
            inputSchema=tool["inputSchema"],
        )
        strands_mcp_tools.append(MCPAgentTool(mcp_tool, client))
    return strands_mcp_tools

