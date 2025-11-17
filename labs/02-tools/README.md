## Introduction to Life Sciences Research Tools

Agents require tools to execute actions and generate insights from trusted data sources. The broad tool categories for life sciences are 4 types:

- Public biomedical databases that provide various types of data over APIs or MCP servers
- Internal data catalogs residing within a customer AWS environment with different types of databases
- Statistical tools that can run biocontainers/custom code/ generate dynamic code based on a specific runtime environment
- Biology Foundation models (BioFMs) that can execute specific downstream tasks for different types of data modalities

Among these capabilities, public biomedical databases have seen a rapid proliferation over the years but are hard to harmonize and integrate with existing internal workflows. Specifically, we look at specialized databases made available via Biomni, a general-purpose biomedical AI agent¹. The tools used include 

MCP (Model Context Protocol) is an open-source standard for connecting AI applications to external systems. Using MCP, agents can connect to data sources (e.g. local files, databases), tools (e.g. search engines, calculators) and workflows (e.g. specialized prompts)—enabling them to access key information and perform tasks. Specifically, we look at AWS MCP Servers that use this protocol to provide agents access to AWS documentation, contextual guidance, and best practices².

Implementing a reusable tool gateway that can handle concurrent requests from research agent, proper authentication, and consistent performance becomes critical at scale. The gateway must enable agents to discover and use tools through secure endpoints, help agents find the right tools through contextual search capabilities, and manage both inbound authentication (verifying agent identity) and outbound authentication (connecting to external biomedical databases) in a unified service. Without this architecture, research teams face authentication complexity and reliability issues that prevent effective scaling. The AgentCore Gateway service centralizes Biomni database tools as more secure, reusable endpoints with semantic search capabilities³.

You can read more on our blog [Build a biomedical research agent with Biomni tools and Amazon Bedrock AgentCore Gateway](https://aws.amazon.com/blogs/machine-learning/build-a-biomedical-research-agent-with-biomni-tools-and-amazon-bedrock-agentcore-gateway/)

## Module Overview

In this module, you'll implement a research agent using [Amazon Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html) with access to over 30 specialized biomedical database tools from [Biomni](https://biomni.stanford.edu/), thereby accelerating scientific discovery while maintaining enterprise-grade security and production scale. You will also leverage the best practices for building end to end templates with Bedrock AgentCore including components like AgentCore Memory for memory management. 

Through the two  notebooks in this module, you'll master the essential techniques for augmenting research agents with existing reusable tools and also deploying your own tools. 

## Lab Details

**1. Augment your agent with a pre-deployed tools gateway :** Connect the pre-deployed entperise gateway that has 30+ database tools from Biomni via a MCP client, search and filter most relevant tools based on query and deploy a research agent that can use this gateway for biomedical research.

**2. Bring your own tool to the gateway:** Learn how to add your own tools to the gateway with multiple options including AWS Lambda, OpenAPIs, Smithy targets and MCP servers. You will then add a remote MCP server to the gateway.

## Sources

1. [Biomni](https://biomni.stanford.edu/).

2. [AWS MCP servers](https://awslabs.github.io/mcp/)

3. [Amazon Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)