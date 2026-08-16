# Arya — AI Sales Agent (RAG-based)

Arya is a Retrieval-Augmented Generation (RAG) sales agent built for a trading company use case. It answers customer queries by retrieving relevant context from a vector database of company knowledge, then generates grounded responses using an LLM — with automatic lead scoring to route high-intent customers to a human sales team.

## What it does

- Answers customer questions using context retrieved from a knowledge base (catalogue, pricing, logistics, payment terms, FAQs)
- Scores incoming leads as hot / warm / cold based on conversation signals
- Automatically flags high-intent leads for escalation to a human sales rep
- Designed for WhatsApp deployment via webhook integration

## Tech stack

- **Language:** Python
- **Vector store:** ChromaDB
- **Embeddings:** nomic-embed-text
- **LLM:** Groq (LLM inference)
- **Knowledge base:** 7 structured markdown documents (catalogue, pricing, logistics, payment terms, FAQs)

## Project structure

```
├── agent.py                 # Core RAG agent logic — retrieval + response generation + lead scoring
├── webhook.py                # Webhook handler for WhatsApp-style message integration
├── load_knowledge_base.py    # Script to embed and load knowledge base docs into ChromaDB
├── kb/                       # Source knowledge base markdown documents
├── indogulf_db/               # Persisted ChromaDB vector store
└── requirements.txt          # Python dependencies
```

## How it works

1. `load_knowledge_base.py` chunks and embeds the markdown knowledge base into ChromaDB using nomic-embed-text embeddings.
2. `agent.py` handles incoming queries: retrieves the most relevant chunks from ChromaDB, passes them as context to the Groq LLM, and generates a grounded response.
3. Alongside the response, the agent applies rule-based logic to score the lead (hot / warm / cold) and flags high-intent conversations for human escalation.
4. `webhook.py` exposes an endpoint so the agent can be plugged into a WhatsApp-style messaging flow.

## Setup

```bash
pip install -r requirements.txt
python load_knowledge_base.py   # builds the vector store from kb/
python agent.py                  # run the agent (or webhook.py for webhook mode)
```

> Note: API keys (e.g. Groq) are expected via environment variables, not hardcoded in source.

## Status

Tested end-to-end via a terminal-based conversational demo. WhatsApp webhook integration designed but demoed locally.
