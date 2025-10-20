import argparse
import asyncio
import datetime
import json
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator

# Configure the root strands logger
logging.getLogger("strands").setLevel(logging.INFO)

logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


# Create a custom tool
@tool
def weather():
    """Get weather"""  # Dummy implementation
    return "sunny"


# Define model
model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
)

# Define agent
agent = Agent(
    model=model,
    tools=[calculator, weather],
    system_prompt="You're a helpful assistant. You can do simple math calculation, and tell the weather.",
)


# Define Bedrock AgentCore app
app = BedrockAgentCoreApp()


# Define Bedrock AgentCore entrypoint
@app.entrypoint
def strands_agent_bedrock(payload, context):
    """
    Invoke the agent with a payload
    """
    user_input = payload.get("prompt")
    print("User input: ", user_input)
    try:
        result = agent(user_input)
        print()
        return {"result": result.message}
    except Exception as e:
        return {"Error": str(e)}


# Start Bedrock AgentCore app
if __name__ == "__main__":
    app.run()
    # strands_agent_bedrock({"payload": "What is 2+14?"}, None)
