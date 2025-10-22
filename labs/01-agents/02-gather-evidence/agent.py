import asyncio

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from search_pmc import search_pmc_tool
from gather_evidence import gather_evidence_tool
from strands import Agent
from strands.models import BedrockModel
from config import MODEL_ID, SYSTEM_PROMPT

app = BedrockAgentCoreApp()

model = BedrockModel(
    model_id=MODEL_ID,
)
agent = Agent(
    model=model,
    tools=[search_pmc_tool, gather_evidence_tool],
    system_prompt=SYSTEM_PROMPT,
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

            # Print tool use
            for content in event.get("message", {}).get("content", []):
                if tool_use := content.get("toolUse"):
                    yield "\n"
                    yield f"🔧 Using tool: {tool_use['name']}"
                    for k, v in tool_use["input"].items():
                        yield f"**{k}**: {v}\n"
                    yield "\n"

            # Print event data
            if "data" in event:
                yield event["data"]
    except Exception as e:
        yield f"Error: {str(e)}"


if __name__ == "__main__":
    app.run()
