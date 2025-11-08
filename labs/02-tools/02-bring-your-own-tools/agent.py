from database_tools import get_gateway_access_token, get_all_mcp_tools_from_mcp_client, tool_search, tools_to_strands_mcp_tools
from utils import get_ssm_parameter
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands_tools import current_time
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import time
import uuid
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

MAX_TOOLS=10

SYSTEM_PROMPT = """
    You are a Healthcare Research Infrastructure Assistant specializing in AWS-powered life sciences solutions.

CAPABILITIES:
- AWS Infrastructure: Access AWS documentation, regional availability, service recommendations, and CloudFormation templates via AWS Knowledge tools
- Research Data: Query clinical trials database, patient outcomes, biomarker studies, and proprietary research data via database tools

APPROACH:
1. Understand the research or infrastructure need
2. Use AWS Knowledge tools for architecture, services, compliance, and regional availability
3. Use database tools to validate with real research data or inform design decisions
4. Combine both sources to provide data-driven, compliant AWS solutions

GUIDELINES:
- Prioritize HIPAA/GDPR compliance for healthcare data
- Consider cost optimization for large-scale research workloads
- Validate architectural decisions with actual research data when available
- Provide specific AWS service recommendations with regional availability
- Include relevant code samples or CloudFormation snippets when helpful

Be concise, technical, and always ground recommendations in both AWS best practices and real research context.

    """

app = BedrockAgentCoreApp()


@app.entrypoint
async def strands_agent_bedrock(payload):
    
    """Create and run agent for each invocation"""

    # Create model
    model = BedrockModel(
        model_id="global.anthropic.claude-sonnet-4-20250514-v1:0",
        additional_request_fields={
            "anthropic_beta": ["interleaved-thinking-2025-05-14"],
            "thinking": {"type": "enabled", "budget_tokens": 8000},
        },
    )
    # Get gateway access token
    jwt_token = get_gateway_access_token()
    if not jwt_token:
        print("❌ Failed to get gateway access token")
        
    # Get gateway endpoint
    gateway_endpoint = get_ssm_parameter("/deep-research-workshop/agentcore/gateway_url")
    print(f"Gateway Endpoint - MCP URL: {gateway_endpoint}")

    # Create MCP client
    client = MCPClient(
        lambda: streamablehttp_client(
            gateway_endpoint, headers={"Authorization": f"Bearer {jwt_token}"}
        )
    )

    # Configure memory
    mem_arn = get_ssm_parameter("/deep-research-workshop/agentcore/memory_id")
    mem_id = mem_arn.split("/")[-1]

    user_input = payload.get("prompt")
    actor_id = payload.get("actor_id", "DEFAULT")
    session_id = payload.get("session_id", "DEFAULT")

    if not session_id:
        raise Exception("Context session_id is not set")
    
    agentcore_memory_config = AgentCoreMemoryConfig(
        memory_id=mem_id,
        session_id=session_id,
        actor_id=actor_id
    )
        
    session_manager = AgentCoreMemorySessionManager(
        agentcore_memory_config=agentcore_memory_config
    )

    

    client.start()
    # Use semantic tool search 
    search_query_to_use = user_input
    print(f"\n🔍 Searching for tools with query: '{search_query_to_use}'")
                
    start_time = time.time()
    tools_found = tool_search(gateway_endpoint, jwt_token, search_query_to_use, max_tools=MAX_TOOLS)
    search_time = time.time() - start_time
                
    if not tools_found:
        print("❌ No tools found from search")
                    
    print(f"✅ Found {len(tools_found)} relevant tools in {search_time:.2f}s")
    print(f"Top tool: {tools_found[0]['name']}")
                
    agent_tools = tools_to_strands_mcp_tools(tools_found, MAX_TOOLS, client)
    agent = Agent(system_prompt=SYSTEM_PROMPT,model=model, tools=agent_tools, session_manager=session_manager, agent_id=str(uuid.uuid4()))

    print("User input:", user_input)
    # Stream response
    tool_name = None
    try:
        async for event in agent.stream_async(user_input):
            if (
                "current_tool_use" in event
                and event["current_tool_use"].get("name") != tool_name
            ):
                tool_name = event["current_tool_use"]["name"]
                yield f"\n\n🔧 Using tool: {tool_name}\n\n"
            elif "message" in event and "content" in event["message"]:
                for obj in event["message"]["content"]:
                    if "toolResult" in obj:
                        pass  # Skip tool result display
                    elif "reasoningContent" in obj:
                        reasoning_text = obj["reasoningContent"]["reasoningText"]["text"]
                        yield f"\n\n🔧 Reasoning: {reasoning_text}\n\n"
            if "data" in event:
                tool_name = None
                yield event["data"]
    except Exception as e:
        yield f"Error processing request: {str(e)}"
    finally:
        #client.close()
        try:
            client.close()
        except AttributeError:
            # MCPClient might not have close method in this version
            pass
        except Exception as e:
            print(f"Warning: Error during client cleanup: {e}")
        


if __name__ == "__main__":
    app.run()
