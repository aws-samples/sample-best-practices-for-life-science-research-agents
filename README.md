# Best Practices for Life Science Research Agents on AWS

## Summary

Learn how to build and deploy AI agents for life science research. AI research agents speed up scientific discovery by planning research tasks, interacting with domain-specific tools and data, and generating detailed research reports. This hands-on workshop will cover current best practices for building AI research agents. Through interactive demonstrations and hands-on exercises, you'll learn how to use AWS services like Amazon Bedrock AgentCore and open source frameworks like Strands Agents to deploy AI research teams securely and at scale. Then, you'll experiment with scientific tools and databases to answer your own research questions. Whether you're hunting for the next blockbuster drug or pushing the boundaries of basic research, you'll leave equipped with practical skills to accelerate your scientific pipeline.

## Getting Started

### Installation (One Command!)

After cloning this repository in JupyterLab, open a terminal and run:

```bash
cd sample-best-practices-for-life-science-research-agents
pip install -e .
```

This installs all dependencies including the interactive chat CLI.

### Using the Chat CLI

After completing the notebooks and deploying your agent to AgentCore, you can interact with it using the chat CLI:

```bash
agentcore-chat
```

The CLI will:

1. Automatically discover your deployed agents
2. Let you select which agent to chat with
3. Start an interactive chat session

Type `exit` to quit the chat session.

## What's Included

- All required Python packages (strands-agents, boto3, etc.)
- The `agentcore-chat` CLI tool for interactive agent testing
- Hands-on workshop notebooks and examples

## Project Structure

```bash
sample-best-practices-for-life-science-research-agents/
├── src/
│   └── workshop_tools/          # Chat CLI code
├── labs/                        # Example notebooks
└── pyproject.toml               # Project configuration
```
