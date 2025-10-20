import argparse
import asyncio
import json

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator  # Import the calculator tool
import datetime

app = BedrockAgentCoreApp()


# Create a custom tool
@tool
def weather():
    """Get weather"""  # Dummy implementation
    return "sunny"


model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
model = BedrockModel(
    model_id=model_id,
)
agent = Agent(
    model=model,
    tools=[calculator, weather],
    system_prompt="You're a helpful assistant. You can do simple math calculation, and tell the weather.",
)


@app.entrypoint
async def strands_agent_bedrock(payload):
    """
    Invoke the agent with a payload
    """
    user_input = payload.get("prompt")
    print("User input:", user_input)
    try:
        async for event in agent.stream_async(user_input):
            # Track event loop lifecycle
            if event.get("init_event_loop", False):
                print("🔄 Event loop initialized")
            elif event.get("start_event_loop", False):
                print("▶️ Event loop cycle starting")
                yield f"start_event_loop: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"
            elif event.get("start", False):
                print("📝 New cycle started")
            elif "message" in event:
                print(f"📬 New message created: {event['message']['role']}")
            elif event.get("force_stop", False):
                print(
                    f"🛑 Event loop force-stopped: {event.get('force_stop_reason', 'unknown reason')}"
                )

            # Track tool usage
            if "current_tool_use" in event and event["current_tool_use"].get("name"):
                tool_name = event["current_tool_use"]["name"]
                print(f"🔧 Using tool: {tool_name}")
                yield f"🔧 Using tool: {tool_name}"

            if "data" in event:
                yield event["data"]
    except Exception as e:
        yield f"Error: {str(e)}"


if __name__ == "__main__":
    app.run()
