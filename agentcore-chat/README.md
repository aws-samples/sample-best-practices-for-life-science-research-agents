# Amazon Bedrock AgentCore Chat

A terminal-based conversational AI interface to test and demonstrate Amazon Bedrock AgentCore Runtime integration.

## Overview

**agentcore-chat** serves as both a working chat application and a reference implementation for building conversational AI agents on AWS. It showcases how to integrate custom tools, deploy to AWS infrastructure, and provide streaming responses through a clean terminal interface.

## Key Features

- **Conversational AI**: Powered by Amazon Bedrock models
- **Streaming Responses**: Real-time event tracking and response streaming
- **AWS Deployment**: Production-ready deployment via Bedrock AgentCore Runtime
- **Container Support**: Docker-based cloud deployment
- **Terminal Interface**: Clean CLI built with Click framework
- **Flexible Setup**: Support for both cloud-native and local development workflows

## Technology Stack

- **Python 3.12** - Core language
- **Amazon Bedrock AgentCore** - AWS runtime platform
- **Strands Agents** - Agent framework with tool integration
- **Click** - CLI framework
- **Docker** - Containerization
- **uv** - Modern Python package manager
- **Boto3** - AWS SDK for Python

## Installation

### Prerequisites

- Python 3.12+
- AWS credentials configured (for deployment)

### Install uv Package Manager

First, install `uv`, a fast Python package manager:

**macOS and Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

For more installation options, see the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

### Install project

```bash
# Clone and install
git clone <repository-url>
cd agentcore-chat
uv sync

# Commands are now available globally
uv run chat
```

### Deploy Amazon Bedrock AgentCore Examples

#### Basic example

```bash
cd examples/basic
uv run agentcore configure --entrypoint basic_agent.py --disable-memory --non-interactive
uv run agentcore launch
uv run agentcore status
uv run agentcore invoke '{"prompt": "Hello"}' 
```

#### Streaming example

```bash
cd examples/streaming
uv run agentcore configure --entrypoint streaming_agent.py --disable-memory --non-interactive
uv run agentcore launch
uv run agentcore status
uv run agentcore invoke '{"prompt": "Hello"}' 
```

## Usage Examples

### Basic Chat

Start an interactive chat session:

```bash
uv run chat
```

The CLI will:

1. List all available agent runtimes in your AWS account
2. Prompt you to select an agent
3. Start an interactive chat session using IAM authentication

## Project Structure

```bash
├── src/agentcore_chat/          # Main package source code
│   ├── models.py                # Data models
│   ├── chat.py                  # CLI chat interface
│   ├── chat_session.py          # Chat session management
│   ├── agent_client.py          # Agent communication
│   └── response_handler.py      # Response processing
└── examples/                    # Reference implementation
    ├── basic/                   # Basic agent example
    └── streaming/         # Streaming agent example
```

## Support

For questions and support, please refer to the AWS Bedrock AgentCore and Strands Agents documentation.
