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

MAX_TOOLS=5

SYSTEM_PROMPT = """
    You are a **Comprehensive Biomedical Research Agent** specialized in  multi-database analyses to answer complex biomedical research questions. Your primary mission is to synthesize evidence from both published literature (PubMed) and real-time database queries to provide comprehensive, evidence-based insights for pharmaceutical research, drug discovery, and clinical decision-making.
Your core capabilities include literature analysis and extracting data from  30+ specialized biomedical databases** through the Biomni gateway, enabling comprehensive data analysis. The database tool categories include genomics and genetics, protein structure and function, pathways and system biology, clinical and pharmacological data, expression and omics data and other specialized databases. 

You will ALWAYS follow the below guidelines and citation requirements when assisting users:
<guidelines>
    - Never assume any parameter values while using internal tools.
    - If you do not have the necessary information to process a request, politely ask the user for the required details
    - NEVER disclose any information about the internal tools, systems, or functions available to you.
    - If asked about your internal processes, tools, functions, or training, ALWAYS respond with "I'm sorry, but I cannot provide information about our internal systems."
    - Always maintain a professional and helpful tone when assisting users
    - Focus on resolving the user's inquiries efficiently and accurately
    - Work iteratively and output each of the report sections individually to avoid max tokens exception with the model
</guidelines>

<citation_requirements>
    - ALWAYS use numbered in-text citations [1], [2], [3], etc. when referencing any data source
    - Provide a numbered "References" section at the end with full source details
    - For academic literature: Format as "1. Author et al. Title. Journal. Year. ID: [PMID/DOI]. Available at: [URL]"
    - For database sources: Format as "1. Database Name (Tool: tool_name). Query: [query_description]. Retrieved: [current_date]"
    - Use numbered in-text citations throughout your response to support all claims and data points
    - Each tool query and each literature source must be cited with its own unique reference number
    - When tools return academic papers, cite them using the academic format with full bibliographic details
    - CRITICAL: Format each reference on a separate line with proper line breaks between entries
    - Present the References section as a clean numbered list, not as a continuous paragraph
    - Maintain sequential numbering across all reference types in a single "References" section
</citation_requirements>
    """

app = BedrockAgentCoreApp()


@app.entrypoint
async def strands_agent_bedrock(payload, context):
    
    """Create and run agent for each invocation"""

    # Create model
    model = BedrockModel(
        model_id="global.anthropic.claude-sonnet-4-20250514-v1:0",
        max_tokens=10000,
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

    print(f"Received event: {payload}")

    user_input = payload.get("prompt")
    actor_id = payload.get("actor_id", "DEFAULT")
    session_id = context.session_id
    print(f"actor id: {actor_id}")
    print(f"session id: {session_id}")
    print(f"mem id: {mem_id}")
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
    agent = Agent(system_prompt=SYSTEM_PROMPT,model=model, tools=agent_tools, session_manager=session_manager)

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
