import asyncio

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from search_pmc import search_pmc_tool
from strands import Agent
from strands.models import BedrockModel

MODEL_ID = "global.anthropic.claude-sonnet-4-20250514-v1:0"

SYSTEM_PROMPT = """You are a life science research assistant. When given a scientific question, follow this process:

1. Use search_pmc_tool with max_search_result_count between 200 and 500 and max_filtered_result_count between 10 and 20 to find highly-cited papers. Search broadly first, then narrow down. Use temporal filters like "last 5 years"[dp] for recent work. 
2. Extract and summarize the most relevant clinical findings.
3. Return structured, well-cited information with PMC ID references.
4. Return URL links associated with PMCID references
"""

app = BedrockAgentCoreApp()

model = BedrockModel(
    model_id=MODEL_ID,
)
agent = Agent(
    model=model,
    tools=[search_pmc_tool],
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
