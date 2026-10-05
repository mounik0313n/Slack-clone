# AI and automation

The AI subsystem is designed as an abstraction layer with a provider interface. The platform supports OpenAI-compatible endpoints, local model runtimes, and compatible adapters.

## Core principles

- AI tools run through authorization-checked service layers
- tool use is audited and rate-limited
- AI features are asynchronous and isolated from core messaging flows
- retention, tenancy, and permission boundaries are enforced before tool execution

## Supported workflows

- conversation summaries
- thread summarization
- semantic search assistance
- task generation
- workflow suggestions
- enterprise knowledge retrieval
