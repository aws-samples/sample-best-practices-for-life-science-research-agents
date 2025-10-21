"""Service for managing AWS Bedrock AgentCore runtime operations."""

import time
import random
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import boto3
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
    EndpointConnectionError,
    ConnectionError,
    ConnectTimeoutError,
    ReadTimeoutError,
    BotoCoreError,
)


@dataclass
class AgentRuntime:
    """Represents an AWS Bedrock AgentCore runtime."""

    arn: str
    name: str
    id: str
    version: str
    description: Optional[str]
    status: str
    last_updated: datetime

    def __post_init__(self) -> None:
        """Validate the AgentRuntime data after initialization."""
        if not self.arn:
            raise ValueError("AgentRuntime ARN cannot be empty")
        if not self.name:
            raise ValueError("AgentRuntime name cannot be empty")
        if not self.id:
            raise ValueError("AgentRuntime ID cannot be empty")
        if not self.version:
            raise ValueError("AgentRuntime version cannot be empty")
        if not self.status:
            raise ValueError("AgentRuntime status cannot be empty")

        # Validate status is one of the expected values
        valid_statuses = {
            "READY",
            "CREATING",
            "CREATE_FAILED",
            "UPDATING",
            "UPDATE_FAILED",
            "DELETING",
        }
        if self.status not in valid_statuses:
            raise ValueError(
                f"Invalid status '{self.status}'. Must be one of: {valid_statuses}"
            )


class AgentRuntimeError(Exception):
    """Base exception for agent runtime operations."""

    pass


class NoAgentsAvailableError(AgentRuntimeError):
    """Raised when no ready agents are found in the AWS account."""

    pass


class AgentRuntimeService:
    """Service class for AWS Bedrock AgentCore Control API interactions.

    Handles listing agent runtimes, filtering for ready agents, and mapping
    agent names to ARNs. Includes comprehensive error handling and pagination support.
    """

    def __init__(self, region_name: Optional[str] = None):
        """Initialize the AgentRuntimeService with AWS client.

        Args:
            region_name: AWS region name. If None, uses default boto3 region resolution.

        Raises:
            AgentRuntimeError: If AWS credentials are not available or client creation fails.
        """
        try:
            self.client = boto3.client(
                "bedrock-agentcore-control", region_name=region_name
            )
            # Store the region for OAuth endpoint URL construction
            self.region = region_name or self.client.meta.region_name
            # Test credentials by attempting to get caller identity
            sts_client = boto3.client("sts", region_name=region_name)
            sts_client.get_caller_identity()
        except NoCredentialsError as e:
            raise AgentRuntimeError(
                "AWS credentials not found. Please configure your AWS credentials using:\n"
                "  • AWS CLI: aws configure\n"
                "  • Environment variables: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY\n"
                "  • IAM roles (for EC2/Lambda)\n"
                "  • AWS credential files (~/.aws/credentials)"
            ) from e
        except PartialCredentialsError as e:
            raise AgentRuntimeError(
                "Incomplete AWS credentials found. Please ensure both AWS_ACCESS_KEY_ID "
                "and AWS_SECRET_ACCESS_KEY are set, or use a complete credential profile."
            ) from e
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "InvalidUserID.NotFound":
                raise AgentRuntimeError(
                    "AWS credentials are invalid or expired. Please check your credentials "
                    "and ensure they are current."
                ) from e
            elif error_code == "AccessDenied":
                raise AgentRuntimeError(
                    "AWS credentials don't have sufficient permissions. Please ensure your "
                    "credentials have access to Bedrock AgentCore and STS services."
                ) from e
            else:
                raise AgentRuntimeError(f"AWS authentication failed: {str(e)}") from e
        except (EndpointConnectionError, ConnectionError, ConnectTimeoutError) as e:
            raise AgentRuntimeError(
                "Unable to connect to AWS services. Please check your internet connection "
                "and ensure AWS endpoints are accessible."
            ) from e
        except Exception as e:
            raise AgentRuntimeError(f"Failed to create AWS client: {str(e)}") from e

    def list_available_agents(self) -> List[AgentRuntime]:
        """Retrieve and filter agent runtimes that are ready and use HTTP protocol.

        Filters agents in two stages:
        1. Status filtering: Only includes agents with status 'READY'
        2. Protocol filtering: Only includes agents with serverProtocol 'HTTP'

        Returns:
            List of AgentRuntime objects with status 'READY' and HTTP protocol, sorted by name.

        Raises:
            AgentRuntimeError: If AWS API call fails or protocol configuration cannot be fetched.
            NoAgentsAvailableError: If no ready agents or no HTTP protocol agents are found.
        """
        try:
            all_agents = self._fetch_all_agents()
            ready_agents = [agent for agent in all_agents if agent.status == "READY"]

            if not ready_agents:
                # Provide more detailed information about available agents
                if all_agents:
                    status_counts = {}
                    for agent in all_agents:
                        status_counts[agent.status] = (
                            status_counts.get(agent.status, 0) + 1
                        )

                    status_info = ", ".join(
                        [f"{count} {status}" for status, count in status_counts.items()]
                    )
                    raise NoAgentsAvailableError(
                        f"No ready agent runtimes found in your AWS account. "
                        f"Found {len(all_agents)} total agents: {status_info}. "
                        f"Please wait for agents to reach 'READY' status or deploy new agents."
                    )
                else:
                    raise NoAgentsAvailableError(
                        "No agent runtimes found in your AWS account. "
                        "Please deploy agents using the Bedrock AgentCore service."
                    )

            # Filter by HTTP protocol after status filtering
            http_agents = self._filter_http_protocol_agents(ready_agents)

            if not http_agents:
                # Handle case where no HTTP protocol agents are available
                self._handle_no_http_agents_error(ready_agents)

            # Sort by name for consistent presentation
            http_agents.sort(key=lambda agent: agent.name)
            return http_agents

        except NoAgentsAvailableError:
            raise
        except (ClientError, BotoCoreError) as e:
            self._handle_aws_error(e, "list_agents")
        except (
            EndpointConnectionError,
            ConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
        ) as e:
            raise AgentRuntimeError(
                "Network error while connecting to AWS services. Please check your internet "
                "connection and try again."
            ) from e
        except Exception as e:
            raise AgentRuntimeError(f"Unexpected error listing agents: {str(e)}") from e

    def get_agent_by_name(self, name: str) -> Optional[AgentRuntime]:
        """Find an agent runtime by its name.

        Args:
            name: The agentRuntimeName to search for.

        Returns:
            AgentRuntime object if found, None otherwise.

        Raises:
            AgentRuntimeError: If AWS API call fails.
        """
        if not name or not name.strip():
            raise AgentRuntimeError("Agent name cannot be empty")

        try:
            available_agents = self.list_available_agents()
            for agent in available_agents:
                if agent.name == name:
                    return agent
            return None
        except (AgentRuntimeError, NoAgentsAvailableError):
            raise
        except (
            EndpointConnectionError,
            ConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
        ) as e:
            raise AgentRuntimeError(
                "Network error while searching for agent. Please check your internet "
                "connection and try again."
            ) from e
        except Exception as e:
            raise AgentRuntimeError(
                f"Error finding agent by name '{name}': {str(e)}"
            ) from e

    def _get_agent_runtime_details(self, agent_id: str, version: str) -> Dict[str, Any]:
        """Fetch detailed agent runtime configuration from AWS API.

        Calls the get-agent-runtime API to retrieve detailed configuration
        including protocol information for a specific agent runtime.

        Args:
            agent_id: The agentRuntimeId to fetch details for.
            version: The agentRuntimeVersion to fetch details for.

        Returns:
            Dictionary containing the full agent runtime configuration from AWS API.

        Raises:
            AgentRuntimeError: If the API call fails or returns invalid data.
        """
        if not agent_id or not agent_id.strip():
            raise AgentRuntimeError("Agent ID cannot be empty")
        if not version or not version.strip():
            raise AgentRuntimeError("Agent version cannot be empty")

        try:
            response = self.client.get_agent_runtime(
                agentRuntimeId=agent_id, agentRuntimeVersion=version
            )
            return response
        except ClientError as e:
            self._handle_aws_error(e, "get_agent_runtime")
        except (
            EndpointConnectionError,
            ConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
        ) as e:
            raise AgentRuntimeError(
                "Network error while fetching agent runtime details. "
                "Please check your internet connection and try again."
            ) from e
        except BotoCoreError as e:
            self._handle_aws_error(e, "get_agent_runtime")
        except Exception as e:
            raise AgentRuntimeError(
                f"Unexpected error fetching agent runtime details: {str(e)}"
            ) from e

    def _extract_protocol_from_response(
        self, response: Dict[str, Any]
    ) -> Optional[str]:
        """Extract protocol configuration from get-agent-runtime API response.

        Parses the protocolConfiguration.serverProtocol field from the API response
        and validates that it contains a supported protocol value.

        Args:
            response: The full response dictionary from get-agent-runtime API call.

        Returns:
            The server protocol string ("HTTP" or "MCP") if found and valid,
            None if missing, malformed, or contains an unsupported protocol value.
        """
        if not isinstance(response, dict):
            return None

        try:
            protocol_config = response.get("protocolConfiguration", {})
            if not isinstance(protocol_config, dict):
                return None

            server_protocol = protocol_config.get("serverProtocol")
            if not isinstance(server_protocol, str):
                return None

            # Validate protocol value - only return known supported protocols
            if server_protocol in ["HTTP", "MCP"]:
                return server_protocol
            else:
                # Log unexpected protocol value but don't fail
                # This allows for graceful handling of new protocol types
                return None

        except (KeyError, TypeError, AttributeError):
            # Handle any unexpected response structure
            return None

    def _filter_http_protocol_agents(
        self, agents: List[AgentRuntime]
    ) -> List[AgentRuntime]:
        """Filter agents to only include those using HTTP protocol.

        Fetches protocol configuration for each agent and filters to only include
        agents where protocolConfiguration.serverProtocol equals "HTTP".
        Agents with missing or malformed protocol configurations are excluded.

        Args:
            agents: List of AgentRuntime objects to filter.

        Returns:
            List of AgentRuntime objects that use HTTP protocol.

        Raises:
            AgentRuntimeError: If all protocol configuration fetches fail.
        """
        if not agents:
            return []

        http_agents = []
        fetch_errors = []

        for agent in agents:
            try:
                response = self._get_agent_runtime_details(agent.id, agent.version)
                protocol = self._extract_protocol_from_response(response)
                if protocol == "HTTP":
                    http_agents.append(agent)
            except AgentRuntimeError as e:
                fetch_errors.append(f"Agent {agent.name}: {str(e)}")
            except Exception as e:
                fetch_errors.append(f"Agent {agent.name}: Unexpected error - {str(e)}")

        # If we couldn't fetch protocol info for any agents, that's a problem
        if not http_agents and len(agents) > 0 and len(fetch_errors) == len(agents):
            error_summary = "; ".join(fetch_errors[:3])
            if len(fetch_errors) > 3:
                error_summary += f" (and {len(fetch_errors) - 3} more)"

            raise AgentRuntimeError(
                f"Failed to fetch protocol configuration for all {len(agents)} agents. "
                f"Errors: {error_summary}"
            )

        return http_agents

    def _handle_no_http_agents_error(self, ready_agents: List[AgentRuntime]) -> None:
        """Handle the case where no HTTP protocol agents are available.

        Provides informative error messages that distinguish between no ready agents
        vs no HTTP protocol agents, helping users understand the protocol filtering
        behavior and suggesting actionable solutions.

        Args:
            ready_agents: List of agents that passed the READY status filter.

        Raises:
            NoAgentsAvailableError: Always raises with appropriate error message
                explaining the protocol filtering and suggesting solutions.
        """
        if not ready_agents:
            raise NoAgentsAvailableError(
                "No ready agent runtimes found in your AWS account. "
                "Please deploy agents using the Bedrock AgentCore service and wait "
                "for them to reach 'READY' status."
            )

        # Build detailed error message explaining the protocol filtering
        agent_names = [agent.name for agent in ready_agents[:3]]  # Show first 3 names
        agent_list = ", ".join(agent_names)
        if len(ready_agents) > 3:
            agent_list += f" (and {len(ready_agents) - 3} more)"

        error_message = (
            f"No HTTP protocol agent runtimes found. "
            f"Found {len(ready_agents)} ready agents ({agent_list}), "
            f"but none use HTTP protocol. "
            f"\n\nThe agentcore-chat CLI only supports agents with HTTP protocol. "
            f"Your available agents may use MCP or other protocols that are not compatible. "
            f"\n\nTo resolve this issue:\n"
            f"  • Deploy new agents configured with HTTP protocol\n"
            f"  • Check your existing agent configurations in the AWS console\n"
            f"  • Verify that your agents are using 'serverProtocol: HTTP' in their configuration"
        )

        raise NoAgentsAvailableError(error_message)

    def _fetch_all_agents(self) -> List[AgentRuntime]:
        """Fetch all agent runtimes with pagination handling and retry logic.

        Returns:
            List of all AgentRuntime objects from AWS API.

        Raises:
            AgentRuntimeError: If AWS API call fails after retries.
        """
        all_agents = []
        next_token = None
        max_retries = 3
        base_delay = 1.0  # Base delay in seconds

        while True:
            retry_count = 0

            while retry_count <= max_retries:
                try:
                    params = {"maxResults": 100}
                    if next_token:
                        params["nextToken"] = next_token

                    response = self.client.list_agent_runtimes(**params)

                    # Convert API response to AgentRuntime objects
                    for agent_data in response.get("agentRuntimes", []):
                        agent = self._convert_api_response_to_agent_runtime(agent_data)
                        all_agents.append(agent)

                    # Check for more pages
                    next_token = response.get("nextToken")
                    break  # Success, exit retry loop

                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")

                    # Handle retryable errors with exponential backoff
                    if error_code in [
                        "ThrottlingException",
                        "InternalServerException",
                        "ServiceUnavailableException",
                    ]:
                        if retry_count < max_retries:
                            retry_count += 1
                            # Exponential backoff with jitter
                            jitter = random.uniform(0, 0.1 * retry_count)
                            wait_time = min(
                                base_delay * (2 ** (retry_count - 1)) + jitter, 60.0
                            )
                            time.sleep(wait_time)
                            continue
                        else:
                            # Max retries exceeded for retryable errors
                            if error_code == "ThrottlingException":
                                raise AgentRuntimeError(
                                    "Request rate limit exceeded. Please try again later."
                                ) from e
                            else:
                                raise AgentRuntimeError(
                                    "AWS service is temporarily unavailable. Please try again later."
                                ) from e

                    # Non-retryable errors, re-raise immediately
                    raise

                except (
                    EndpointConnectionError,
                    ConnectionError,
                    ConnectTimeoutError,
                    ReadTimeoutError,
                ) as e:
                    if retry_count < max_retries:
                        retry_count += 1
                        # Shorter backoff for network errors
                        wait_time = min(base_delay * retry_count, 10.0)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise AgentRuntimeError(
                            "Network connectivity issues persist. Please check your internet "
                            "connection and AWS service status."
                        ) from e

                except BotoCoreError as e:
                    # Other boto3 errors that might be retryable
                    if retry_count < max_retries:
                        retry_count += 1
                        wait_time = min(base_delay * retry_count, 10.0)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise AgentRuntimeError(f"AWS SDK error: {str(e)}") from e

            # If we have no more pages, we're done
            if not next_token:
                break

        return all_agents

    def _convert_api_response_to_agent_runtime(
        self, agent_data: Dict[str, Any]
    ) -> AgentRuntime:
        """Convert AWS API response data to AgentRuntime object.

        Args:
            agent_data: Dictionary from AWS API response.

        Returns:
            AgentRuntime object.

        Raises:
            AgentRuntimeError: If required fields are missing or invalid.
        """
        try:
            # Parse the lastUpdatedAt timestamp
            last_updated_raw = agent_data.get("lastUpdatedAt")
            if last_updated_raw:
                # Handle different timestamp formats from AWS
                if isinstance(last_updated_raw, str):
                    # ISO format string
                    last_updated = datetime.fromisoformat(
                        last_updated_raw.replace("Z", "+00:00")
                    )
                elif isinstance(last_updated_raw, (int, float)):
                    # Unix timestamp
                    last_updated = datetime.fromtimestamp(last_updated_raw)
                else:
                    # Unknown format, use current time
                    last_updated = datetime.now()
            else:
                last_updated = datetime.now()

            return AgentRuntime(
                arn=agent_data.get("agentRuntimeArn", ""),
                name=agent_data.get("agentRuntimeName", ""),
                id=agent_data.get("agentRuntimeId", ""),
                version=agent_data.get("agentRuntimeVersion", ""),
                description=agent_data.get("description"),
                status=agent_data.get("status", ""),
                last_updated=last_updated,
            )
        except (ValueError, KeyError) as e:
            raise AgentRuntimeError(
                f"Invalid agent runtime data from AWS API: {str(e)}"
            ) from e

    def _handle_aws_error(self, error, operation_context: Optional[str] = None) -> None:
        """Handle AWS errors with user-friendly messages.

        Enhanced to handle get-agent-runtime specific errors and provide
        context-aware error messages based on the operation being performed.

        Args:
            error: The error from boto3 (ClientError or BotoCoreError).
            operation_context: Optional context about which operation failed
                (e.g., "list_agents", "get_agent_runtime", "protocol_fetch").

        Raises:
            AgentRuntimeError: Always raises with appropriate error message.
        """
        if isinstance(error, ClientError):
            error_code = error.response.get("Error", {}).get("Code", "Unknown")
            error_message = error.response.get("Error", {}).get("Message", str(error))

            if error_code == "AccessDeniedException":
                # Provide context-specific permission guidance
                if operation_context == "get_agent_runtime":
                    raise AgentRuntimeError(
                        "AWS credentials don't have permission to get agent runtime details. "
                        "This permission is required to filter agents by protocol configuration.\n\n"
                        "Please ensure your AWS credentials have the following permission:\n"
                        "  • bedrock-agentcore:GetAgentRuntime\n\n"
                        "To resolve this issue:\n"
                        "  1. Contact your AWS administrator to grant the GetAgentRuntime permission\n"
                        "  2. Update your IAM policy to include: bedrock-agentcore:GetAgentRuntime\n"
                        "  3. Verify your credentials have access to the specific agent runtimes\n\n"
                        "Without this permission, the CLI cannot determine which agents use HTTP protocol."
                    ) from error
                elif operation_context == "protocol_fetch":
                    raise AgentRuntimeError(
                        "Failed to fetch protocol configurations due to insufficient permissions. "
                        "The CLI requires GetAgentRuntime permission to filter agents by protocol.\n\n"
                        "Required permissions:\n"
                        "  • bedrock-agentcore:ListAgentRuntimes (to list agents)\n"
                        "  • bedrock-agentcore:GetAgentRuntime (to check protocol configurations)\n\n"
                        "Please contact your AWS administrator to grant these permissions."
                    ) from error
                else:
                    # General access denied for listing operations
                    raise AgentRuntimeError(
                        "AWS credentials don't have permission to access agent runtimes. "
                        "Please ensure your AWS credentials have the following permissions:\n"
                        "  • bedrock-agentcore:ListAgentRuntimes\n"
                        "  • bedrock-agentcore:GetAgentRuntime\n\n"
                        "Contact your AWS administrator to grant these permissions."
                    ) from error
            elif error_code == "UnauthorizedOperation":
                raise AgentRuntimeError(
                    "Your AWS account is not authorized to use Bedrock AgentCore. "
                    "Please ensure your account has access to the service and that "
                    "Bedrock AgentCore is available in your current AWS region."
                ) from error
            elif error_code == "ResourceNotFoundException":
                if operation_context == "get_agent_runtime":
                    raise AgentRuntimeError(
                        "One or more agent runtimes could not be found when fetching protocol details. "
                        "This may occur if agents were deleted after being listed, or if there are "
                        "permission issues accessing specific agent runtimes.\n\n"
                        "Please try again, or check that the agents still exist in your AWS account."
                    ) from error
                else:
                    raise AgentRuntimeError(
                        "The requested AWS resource was not found. This may indicate "
                        "the service is not available in your region or the resource was deleted."
                    ) from error
            elif error_code == "ValidationException":
                if operation_context == "get_agent_runtime":
                    raise AgentRuntimeError(
                        f"Invalid agent runtime ID or version when fetching protocol details: {error_message}\n\n"
                        "This may indicate corrupted agent data. Please try listing agents again."
                    ) from error
                else:
                    raise AgentRuntimeError(
                        f"Invalid request parameters sent to AWS API: {error_message}"
                    ) from error
            elif error_code == "InternalServerException":
                if operation_context in ["get_agent_runtime", "protocol_fetch"]:
                    raise AgentRuntimeError(
                        "AWS Bedrock AgentCore service is experiencing internal issues while "
                        "fetching agent protocol configurations. This is a temporary problem.\n\n"
                        "Please try again in a few minutes. If the issue persists, some agents "
                        "may be temporarily unavailable for protocol filtering."
                    ) from error
                else:
                    raise AgentRuntimeError(
                        "AWS Bedrock AgentCore service is experiencing internal issues. "
                        "This is a temporary problem - please try again in a few minutes."
                    ) from error
            elif error_code == "ServiceUnavailableException":
                raise AgentRuntimeError(
                    "AWS Bedrock AgentCore service is temporarily unavailable. "
                    "Please try again in a few minutes."
                ) from error
            elif error_code == "ThrottlingException":
                if operation_context in ["get_agent_runtime", "protocol_fetch"]:
                    raise AgentRuntimeError(
                        "Request rate limit exceeded while fetching agent protocol configurations. "
                        "The CLI makes multiple API calls to determine agent protocols.\n\n"
                        "Please wait a moment and try again. Consider reducing the number of "
                        "concurrent operations if this issue persists."
                    ) from error
                else:
                    raise AgentRuntimeError(
                        "Request rate limit exceeded for AWS API calls. "
                        "Please wait a moment and try again."
                    ) from error
            elif error_code == "InvalidParameterException":
                if operation_context == "get_agent_runtime":
                    raise AgentRuntimeError(
                        f"Invalid parameters when fetching agent runtime details: {error_message}\n\n"
                        "This may indicate an issue with agent runtime IDs or versions. "
                        "Please try listing agents again."
                    ) from error
                else:
                    raise AgentRuntimeError(
                        f"Invalid parameters in AWS API request: {error_message}"
                    ) from error
            elif error_code == "ConflictException":
                if operation_context == "get_agent_runtime":
                    raise AgentRuntimeError(
                        "Conflict occurred while fetching agent runtime details. "
                        "The agent runtime may be in a transitional state.\n\n"
                        "Please wait a moment and try again."
                    ) from error
                else:
                    raise AgentRuntimeError(
                        f"Conflict in AWS API request: {error_message}"
                    ) from error
            else:
                # Enhanced generic error message with context
                context_info = (
                    f" during {operation_context}" if operation_context else ""
                )
                raise AgentRuntimeError(
                    f"AWS API error{context_info} ({error_code}): {error_message}\n\n"
                    f"If this error persists, please check:\n"
                    f"  • Your AWS credentials and permissions\n"
                    f"  • AWS service status in your region\n"
                    f"  • Network connectivity to AWS services"
                ) from error
        elif isinstance(error, BotoCoreError):
            context_info = f" during {operation_context}" if operation_context else ""
            raise AgentRuntimeError(
                f"AWS SDK error{context_info}: {str(error)}. "
                f"Please check your AWS configuration and network connectivity."
            ) from error
        else:
            context_info = f" during {operation_context}" if operation_context else ""
            raise AgentRuntimeError(
                f"Unexpected AWS error{context_info}: {str(error)}"
            ) from error
