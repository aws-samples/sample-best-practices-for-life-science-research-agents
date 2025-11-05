from utils import get_ssm_parameter
# Get credentials from SSM for Inbound Auth
runtime_client_id = get_ssm_parameter("/deep-research-workshop/agentcore/machine_client_id")
runtime_client_secret = get_ssm_parameter("/deep-research-workshop/agentcore/cognito_secret")
runtime_cognito_discovery_url = get_ssm_parameter("/deep-research-workshop/agentcore/cognito_discovery_url")

import os
from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session

def deploy_mcp_server():
    print("Deploying MCP server to AgentCore Runtime...")
    boto_session = Session()
    region = boto_session.region_name
    print(f"Using AWS region: {region}")

    required_files = ['mcp_server_pubmed.py', 'requirements.txt']
    for file in required_files:
        if not os.path.exists(file):
            raise FileNotFoundError(f"Required file {file} not found")
    print("All required files found ✓")
    agentcore_runtime = Runtime()

    auth_config = {
        "customJWTAuthorizer": {
            "allowedClients": [
                runtime_client_id
            ],
            "discoveryUrl": runtime_cognito_discovery_url
        }
    }

    print("Configuring AgentCore Runtime...")
    response = agentcore_runtime.configure(
        entrypoint="mcp_server_pubmed.py",
        auto_create_execution_role=True,
        auto_create_ecr=True,
        requirements_file="requirements.txt",
        region=region,
        authorizer_configuration=auth_config,
        protocol="MCP",
        agent_name="mcp_server_pubmed"
    )
    print("Configuration completed ✓")

    print("Launching MCP server to AgentCore Runtime...")
    print("This may take several minutes...")
    launch_result = agentcore_runtime.launch()

    agent_arn = launch_result.agent_arn
    agent_id = launch_result.agent_id

    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')

    agent_url = f'https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT'
    print("Launch completed ✓")
    print(f"Agent ARN: {agent_arn}")
    print(f"Agent ID: {agent_id}")

    return agent_url, agent_arn, agent_id