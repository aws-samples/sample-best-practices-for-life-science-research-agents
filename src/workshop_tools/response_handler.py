"""Response handler for processing agent responses from Bedrock AgentCore."""

import json
from typing import Dict, Any, Iterator
import click


class ResponseHandler:
    """Handles different types of responses from the Bedrock AgentCore agent."""

    def __init__(self):
        """Initialize the response handler."""
        self._last_output_was_text = False

    def handle_response(self, response: Dict[str, Any]) -> None:
        """
        Process and display agent response based on content type.

        Args:
            response: Response dictionary from agent client
        """
        # Reset state for new response
        self._last_output_was_text = False

        content_type = response.get("contentType", "")

        # Extract base content type (ignore charset and other parameters)
        base_content_type = content_type.split(";")[0].strip()

        if base_content_type == "text/event-stream":
            self._handle_streaming_response(response.get("response"))
        elif base_content_type == "application/json":
            self._handle_json_response(response.get("response"))
        else:
            # Fallback for unknown content types
            click.echo(f"⚠️  Unknown content type: {content_type}")
            if "response" in response:
                click.echo(str(response["response"]))

    def _handle_streaming_response(self, response_stream) -> None:
        """
        Handle streaming text responses from Bedrock AgentCore.

        Args:
            response_stream: Streaming response from AWS Bedrock AgentCore
        """
        if not response_stream:
            click.echo("⚠️  No response stream received")
            return

        # Reset state for new response
        self._last_output_was_text = False

        try:
            # Handle AWS streaming response format
            if hasattr(response_stream, "iter_lines"):
                # Process line by line for event-stream format
                for line in response_stream.iter_lines(chunk_size=1024):
                    if line:
                        line_str = line.decode("utf-8").strip()
                        self._process_stream_line(line_str)
            else:
                # Handle as raw streaming body
                content = response_stream.read()
                if isinstance(content, bytes):
                    content = content.decode("utf-8")

                # Split content into lines and process each
                lines = content.split("\n")
                for line in lines:
                    line = line.strip()
                    if line:
                        self._process_stream_line(line)

            # Add a newline after streaming is complete
            click.echo()

        except Exception as e:
            click.echo(f"❌ Error processing streaming response: {e}")

    def _process_stream_line(self, line: str) -> None:
        """
        Process a single line from the streaming response.

        Args:
            line: A single line from the stream
        """
        # Skip empty lines
        if not line.strip():
            return

        # Handle Server-Sent Events format (data: prefix)
        if line.startswith("data: "):
            data_content = line[6:]  # Remove "data: " prefix

            # Skip empty data lines or event markers
            if not data_content.strip() or data_content.strip() == "[DONE]":
                return

            self._display_content(data_content)

        # Handle event type lines (event: type)
        elif line.startswith("event: "):
            event_type = line[7:]  # Remove "event: " prefix
            if event_type not in ["ping", "heartbeat"]:  # Skip common keep-alive events
                click.secho(f"🔄 {event_type}", fg="cyan")

        # Handle direct content lines (no prefix)
        else:
            self._display_content(line)

    def _display_content(self, content: str) -> None:
        """
        Display content with proper formatting and JSON parsing.

        Args:
            content: Content string to display
        """
        # Try to parse as JSON first (common for structured responses)
        try:
            json_data = json.loads(content)

            # Handle different JSON response formats
            if isinstance(json_data, dict):
                # Look for common text fields
                text_content = (
                    json_data.get("text")
                    or json_data.get("content")
                    or json_data.get("message")
                    or json_data.get("delta", {}).get("text")
                )

                if text_content:
                    click.secho(text_content, fg="green", nl=False)
                else:
                    # Display the whole dict if no text field found
                    click.secho(str(json_data), fg="green")

            elif isinstance(json_data, str):
                # JSON string content - display directly
                self._format_and_display_text(json_data)

            else:
                # Other JSON types
                click.secho(str(json_data), fg="green", nl=False)

        except json.JSONDecodeError:
            # Not JSON, treat as plain text
            self._format_and_display_text(content)

    def _format_and_display_text(self, text: str) -> None:
        """
        Format and display text content with proper handling of special markers.

        Args:
            text: Text content to format and display
        """
        # Check for Strands-specific event markers
        if self._is_strands_event_marker(text):
            if text.startswith("🔧 Using tool:"):
                # Add newline before tool usage if we just displayed regular text
                if self._last_output_was_text:
                    click.echo()  # Add newline
                formatted_content = self._format_tool_usage(text)
                click.secho(
                    formatted_content, fg="cyan"
                )  # Add newline after tool usage
                self._last_output_was_text = False
            elif text.startswith("start_event_loop:"):
                # Add empty line before timestamp
                click.echo()
                formatted_content = self._format_event_loop_marker(text)
                click.secho(formatted_content, fg="cyan")
                self._last_output_was_text = False
            else:
                click.secho(text, fg="cyan")
                self._last_output_was_text = False
        else:
            # Regular text content - display with proper formatting
            # Handle escaped characters and newlines
            formatted_text = (
                text.replace("\\n", "\n").replace('\\"', '"').replace("\\'", "'")
            )

            # Add newline before regular text if we just displayed an event marker
            if not self._last_output_was_text:
                click.echo()  # Add newline

            # Use echo with color for better terminal compatibility
            click.secho(formatted_text, fg="green", nl=False)
            self._last_output_was_text = True

    def _handle_json_response(self, response_data) -> None:
        """
        Handle JSON responses from the agent.

        Args:
            response_data: JSON response data
        """
        try:
            if isinstance(response_data, str):
                # Parse JSON string
                json_data = json.loads(response_data)
            else:
                # Assume it's already parsed
                json_data = response_data

            # Extract and display just the message content
            message_text = self._extract_message_text(json_data)
            if message_text:
                click.secho(message_text, fg="green")
            else:
                # Fallback to formatted JSON if we can't extract the message
                formatted_json = json.dumps(json_data, indent=2)
                click.secho(formatted_json, fg="green")

        except json.JSONDecodeError as e:
            click.echo(f"❌ Error parsing JSON response: {e}")
            # Fallback to displaying raw content
            click.secho(str(response_data), fg="green")
        except Exception as e:
            click.echo(f"❌ Error processing JSON response: {e}")

    def _format_tool_usage(self, tool_line: str) -> str:
        """
        Format Strands tool usage information with enhanced display.

        Args:
            tool_line: Line containing tool usage information (🔧 Using tool: [name])

        Returns:
            Formatted tool usage string
        """
        # Extract tool name if present
        if ":" in tool_line:
            prefix, tool_name = tool_line.split(":", 1)
            tool_name = tool_name.strip()
            return f"🔧 Using tool: {tool_name}"
        else:
            return tool_line

    def _format_event_loop_marker(self, event_line: str) -> str:
        """
        Format Strands event loop markers to show only timestamp.

        Args:
            event_line: Line containing event loop marker (start_event_loop: [timestamp])

        Returns:
            Formatted timestamp string
        """
        # Extract timestamp if present
        if ":" in event_line:
            prefix, timestamp = event_line.split(":", 1)
            timestamp = timestamp.strip()
            return timestamp
        else:
            return event_line

    def _format_event_marker(self, content: str) -> str:
        """
        Format general event markers for better visibility.

        Args:
            content: Content containing event marker

        Returns:
            Formatted event marker string
        """
        if content.startswith("🔧 Using tool:"):
            return self._format_tool_usage(content)
        elif content.startswith("start_event_loop:"):
            return self._format_event_loop_marker(content)
        else:
            return content

    def _extract_message_text(self, json_data: dict) -> str:
        """
        Extract the message text from JSON response data.
        
        Handles various JSON response formats from different agent types.
        
        Args:
            json_data: Parsed JSON response data
            
        Returns:
            Extracted message text, or empty string if not found
        """
        try:
            # Handle Strands agent format: {"result": {"role": "assistant", "content": [{"text": "..."}]}}
            if isinstance(json_data, dict) and "result" in json_data:
                result = json_data["result"]
                
                # Handle Strands message format
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        first_content = content[0]
                        if isinstance(first_content, dict) and "text" in first_content:
                            return first_content["text"]
                
                # Handle simple string result
                if isinstance(result, str):
                    return result
            
            # Handle direct message formats
            if isinstance(json_data, dict):
                # Look for common message fields
                for field in ["message", "text", "content", "response"]:
                    if field in json_data:
                        value = json_data[field]
                        if isinstance(value, str):
                            return value
            
            # Handle direct string response
            if isinstance(json_data, str):
                return json_data
                
        except Exception:
            # If extraction fails, return empty string to fall back to full JSON display
            return ""

    def _is_strands_event_marker(self, line: str) -> bool:
        """
        Check if line contains Strands-specific event markers.

        Args:
            line: Line to check for event markers

        Returns:
            True if line contains Strands event markers, False otherwise
        """
        strands_markers = [
            "🔧 Using tool:",
            "start_event_loop:",
            "🔄 Event loop",
        ]

        return any(marker in line for marker in strands_markers)
