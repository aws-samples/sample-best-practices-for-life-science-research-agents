import click
import os
import sys
import uuid
from .agent_client import AgentClient, AgentConnectionError, ResponseProcessingError, ChatError
from .response_handler import ResponseHandler
from .agent_runtime_service import (
    AgentRuntimeService,
    AgentRuntime,
    AgentRuntimeError,
    NoAgentsAvailableError,
)
from typing import List, Optional


class AgentSelectionError(Exception):
    """Raised when agent selection fails."""
    pass


def validate_agent_selection(
    user_input: str, available_agents: List[AgentRuntime]
) -> AgentRuntime:
    """Validate user input and return the corresponding AgentRuntime.

    Args:
        user_input: User's selection input (name or number)
        available_agents: List of available AgentRuntime objects

    Returns:
        AgentRuntime: The selected agent runtime object

    Raises:
        AgentSelectionError: If input is invalid or out of range
    """
    user_input = user_input.strip()
    
    if not user_input:
        raise AgentSelectionError("Please enter an agent selection (number or name).")

    # Try numeric selection
    try:
        idx = int(user_input) - 1
        if 0 <= idx < len(available_agents):
            return available_agents[idx]
    except ValueError:
        pass

    # Try name match (case-insensitive)
    for agent in available_agents:
        if agent.name.lower() == user_input.lower():
            return agent

    # No match found
    raise AgentSelectionError(f"Invalid selection: {user_input}")


@click.command()
def chat():
    """Interactive chat with Bedrock AgentCore agent."""
    try:
        # Step 1: Get AWS region from environment
        aws_region = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION")

        # Step 2: Initialize AgentRuntimeService and retrieve available agents
        click.echo("🔍 Retrieving available agent runtimes...")

        try:
            runtime_service = AgentRuntimeService(region_name=aws_region)
        except AgentRuntimeError as e:
            _handle_error(e, "runtime_service")
            return

        try:
            available_agents = runtime_service.list_available_agents()
        except NoAgentsAvailableError as e:
            _handle_error(e, "no_agents")
            return
        except AgentRuntimeError as e:
            _handle_error(e, "runtime_service")
            return

        # Step 3: Display available agents and prompt for selection
        click.echo(f"\n✅ Found {len(available_agents)} ready agent runtime(s):")

        # Create list of agent names for selection
        agent_names = [agent.name for agent in available_agents]

        # Display agents with additional information
        for i, agent in enumerate(available_agents, 1):
            description = f" - {agent.description}" if agent.description else ""
            click.echo(f"  {i}. {agent.name}{description}")

        # Step 4: Prompt user to select an agent
        click.echo()  # Add blank line for better formatting

        selected_agent = None
        while not selected_agent:
            try:
                user_input = click.prompt("Select an agent (name or number)")
                selected_agent = validate_agent_selection(user_input, available_agents)
            except click.Abort:
                # User cancelled selection (Ctrl+C during prompt)
                click.echo("\n👋 Agent selection cancelled. Goodbye!")
                return
            except AgentSelectionError as e:
                click.echo(f"❌ {e}")
                continue
            except Exception as e:
                raise AgentSelectionError(f"Failed to get agent selection: {str(e)}")

        # Step 5: Display selected agent information
        click.echo(f"\n🤖 Selected agent: {selected_agent.name}")
        click.echo(f"   ARN: {selected_agent.arn}")
        if selected_agent.description:
            click.echo(f"   Description: {selected_agent.description}")
        click.echo(f"   Status: {selected_agent.status}")
        click.echo(f"   Version: {selected_agent.version}")
        click.echo(f"   Authentication: IAM")
        click.echo("\n" + "=" * 50)
        click.echo("Starting chat session... (Type 'exit' to close)")
        click.echo("=" * 50 + "\n")

        # Step 6: Start chat session
        try:
            _start_chat_session(selected_agent.arn)
        except AgentConnectionError as e:
            _handle_error(e, "connection")
            return
        except ResponseProcessingError as e:
            _handle_error(e, "response_processing")
            return
        except ChatError as e:
            _handle_error(e, "chat")
            return

    except AgentSelectionError as e:
        _handle_error(e, "agent_selection")
    except KeyboardInterrupt:
        click.echo("\n👋 Chat interrupted. Goodbye!")
    except click.Abort:
        # Re-raise click.Abort to maintain proper CLI exit behavior
        raise
    except Exception as e:
        _handle_error(e, "unexpected")


def _start_chat_session(agent_arn: str, qualifier: str = "DEFAULT") -> None:
    """Start an interactive chat session with the agent.
    
    Args:
        agent_arn: The ARN of the Bedrock AgentCore agent
        qualifier: The agent qualifier (default: "DEFAULT")
    """
    agent_client = AgentClient(agent_arn, qualifier)
    response_handler = ResponseHandler()
    session_id = str(uuid.uuid4())
    
    # Display logo
    _display_logo()
    
    # Display welcome message
    click.echo("Amazon Bedrock AgentCore Chat - Type 'exit' to quit")
    click.echo()
    
    try:
        # Main conversation loop
        while True:
            try:
                # Get user input
                user_input = click.prompt("You", type=str, default="", show_default=False)
                
                # Check for exit command
                if user_input.strip().lower() == "exit":
                    click.echo("👋 Goodbye!")
                    break
                
                # Skip empty messages
                if not user_input.strip():
                    continue
                
                # Send message to agent
                try:
                    response = agent_client.send_message(user_input, session_id)
                    response_handler.handle_response(response)
                except AgentConnectionError as e:
                    click.echo(f"❌ Connection error: {e}. Please try again or type 'exit' to quit.")
                except ResponseProcessingError as e:
                    click.echo(f"⚠️  Response processing error: {e}. Continuing...")
                
                # Add spacing after response
                click.echo()
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                click.echo(f"❌ Unexpected error in conversation loop: {e}")
                click.echo("Type 'exit' to quit or continue chatting.")
    
    except KeyboardInterrupt:
        click.echo("\n👋 Chat interrupted. Goodbye!")
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}")


def _display_logo() -> None:
    """Display the ASCII art logo in orange."""
    logo = """
       %%%%%%%%%%      %%%         %%%%         %%%      %%%%%%%%%      
     %%%%%%%%%%%%%%    %%%%       %%%%%%       %%%%   %%%%%%%%%%%%%%    
     %%        %%%%%   %%%%%      %%%%%%      %%%%%  %%%%%              
                %%%%%   %%%%     %%%%%%%%     %%%%   %%%%               
                %%%%%    %%%%    %%% %%%%    %%%%    %%%%%%             
       %%%%%%%%%%%%%%    %%%%   %%%%  %%%%   %%%%      %%%%%%%%%        
    %%%%%%%%%%%%%%%%%     %%%%  %%%   %%%%  %%%%         %%%%%%%%%%%    
   %%%%%        %%%%%     %%%%  %%%    %%%  %%%%               %%%%%%   
   %%%%%        %%%%%      %%%%%%%%    %%%%%%%%                  %%%%   
   %%%%%       %%%%%%      %%%%%%%      %%%%%%%      %          %%%%%   
    %%%%%%%%%%%% %%%%%      %%%%%%      %%%%%%       %%%%%%%%%%%%%%@    
      %%%%%%%%    %%         %%%%        %%%%         %%%%%%%%%%%       
                                                                        
                                                                        
                                                              ========= 
===                                                       ==============
  =====                                                             ====
     ======                                                   ====  === 
       ==========                                       ========   ==== 
           ===============                      =============      ===  
               ==========================================         ==    
                   =================================                    
                           =================                            
"""
    click.secho(logo, fg=(255, 153, 0))
    click.echo()


def _handle_error(error: Exception, error_type: str) -> None:
    """Unified error handler with context-specific messages.
    
    Args:
        error: The exception that occurred
        error_type: Type of error for context-specific handling
    """
    error_handlers = {
        "runtime_service": {
            "message": "Agent runtime service error",
            "tips": [
                "Check your AWS credentials and permissions",
                "Verify your network connection",
                "Ensure Bedrock AgentCore is available in your region",
                "Try again in a few moments"
            ]
        },
        "no_agents": {
            "message": "No agents available",
            "tips": [
                "Deploy agents using the Bedrock AgentCore service",
                "Wait for existing agents to reach 'READY' status",
                "Check your AWS region and account permissions",
                "Verify agents are deployed in the correct AWS region"
            ]
        },
        "agent_selection": {
            "message": "Agent selection failed",
            "tips": [
                "Restart the command and select a valid agent",
                "Ensure you're selecting from the displayed options",
                "Check that the agent name matches exactly"
            ]
        },
        "session_init": {
            "message": "Failed to initialize chat session",
            "tips": [
                "Agent ARN may be invalid or malformed",
                "Agent may have been deleted or modified after selection",
                "Check AWS credentials and permissions",
                "Verify network connectivity"
            ]
        },
        "connection": {
            "message": "Failed to connect to agent",
            "tips": [
                "Check your AWS credentials and network connection",
                "Verify the agent is still in 'READY' status",
                "Ensure you have permission to invoke the agent",
                "Try restarting the chat session"
            ]
        },
        "response_processing": {
            "message": "Error processing agent response",
            "tips": [
                "The agent response format may be unexpected",
                "Network interruption during response streaming",
                "Agent runtime encountered an internal error",
                "Try sending your message again or restart the session"
            ]
        },
        "chat": {
            "message": "Chat session error",
            "tips": [
                "Try restarting the chat session",
                "Check your network connection",
                "Verify the agent is functioning correctly",
                "Contact support if the issue persists"
            ]
        },
        "unexpected": {
            "message": "Unexpected error",
            "tips": [
                "This is an unexpected error that shouldn't normally occur",
                "Try restarting the application",
                "Check your system resources and network connection",
                "If the issue persists, please report this error"
            ]
        }
    }
    
    handler = error_handlers.get(error_type, error_handlers["unexpected"])
    click.echo(f"❌ {handler['message']}: {error}")
    click.echo("\n🔧 To resolve:")
    for tip in handler["tips"]:
        click.echo(f"  • {tip}")
    
    sys.exit(1)
