"""
IndoGulf Trading — AI Sales Agent (Arya)
=========================================
Receives a WhatsApp message, searches ChromaDB for
relevant knowledge, then calls Groq to generate a reply.

Flow:
    User message
        → ChromaDB (find relevant chunks using nomic-embed-text)
        → Groq API  (generate reply using context + system prompt)
        → Reply sent back

Requirements:
    pip install chromadb groq
    .env file with GROQ_API_KEY=your_key_here
"""

import os
from groq import Groq
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

from dotenv import load_dotenv
load_dotenv()
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "your_groq_api_key_here")
GROQ_MODEL    = "llama-3.1-8b-instant"   # fast, free, great for sales chat
DB_FOLDER     = "./indogulf_db"
COLLECTION    = "indogulf_trading"
OLLAMA_URL    = "http://localhost:11434"
EMBED_MODEL   = "nomic-embed-text"
TOP_K_CHUNKS  = 3                         # how many KB chunks to retrieve

# Load system prompt from file
with open("./kb/00_system_prompt.md", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


# ─────────────────────────────────────────────
# CONNECT TO CHROMADB
# ─────────────────────────────────────────────

embedding_fn = OllamaEmbeddingFunction(
    url=OLLAMA_URL,
    model_name=EMBED_MODEL,
)

db_client  = chromadb.PersistentClient(path=DB_FOLDER)
collection = db_client.get_collection(
    name=COLLECTION,
    embedding_function=embedding_fn,
)

# ─────────────────────────────────────────────
# CONNECT TO GROQ
# ─────────────────────────────────────────────

groq_client = Groq(api_key=GROQ_API_KEY)


# ─────────────────────────────────────────────
# CORE FUNCTIONS
# ─────────────────────────────────────────────

def search_knowledge_base(query: str) -> str:
    """
    Search ChromaDB for the most relevant chunks
    related to the user's message.
    Returns them as a single context string.
    """
    results = collection.query(
        query_texts=[query],
        n_results=TOP_K_CHUNKS,
    )

    # Combine top chunks into one context block
    chunks = results["documents"][0]
    sources = [m["doc"] for m in results["metadatas"][0]]

    context_parts = []
    for chunk, source in zip(chunks, sources):
        context_parts.append(f"[Source: {source}]\n{chunk}")

    return "\n\n---\n\n".join(context_parts)


def score_lead(message: str, history: list) -> str:
    """
    Simple rule-based lead scoring based on message content.
    This runs before the LLM to add metadata.
    """
    message_lower = message.lower()

    hot_signals = [
        "pro forma", "pi", "place order", "how to order",
        "letter of credit", "lc", "tt payment", "wire transfer",
        "ready to buy", "confirm order", "invoice",
        "delivery date", "when can you ship"
    ]
    warm_signals = [
        "price", "cost", "how much", "rate", "moq",
        "minimum", "sample", "interested", "looking for",
        "do you have", "export", "quantity", "details"
    ]

    for signal in hot_signals:
        if signal in message_lower:
            return "HOT"

    for signal in warm_signals:
        if signal in message_lower:
            return "WARM"

    # If it's the first message and just a greeting
    if len(history) <= 1:
        return "COLD"

    return "WARM"  # default after initial contact


def generate_reply(
    user_message: str,
    conversation_history: list,
    lead_name: str = "there"
) -> dict:
    """
    Main agent function.
    1. Search KB for relevant context
    2. Build prompt with context + history
    3. Call Groq for reply
    4. Return reply + lead score + escalation flag
    """

    # Step 1: Get relevant knowledge
    context = search_knowledge_base(user_message)

    # Step 2: Score the lead
    lead_score = score_lead(user_message, conversation_history)

    # Step 3: Build the messages for Groq
    messages = [
        {
            "role": "system",
            "content": f"""{SYSTEM_PROMPT}

---

RELEVANT KNOWLEDGE BASE CONTEXT:
(Use this information to answer the user's question accurately)

{context}

---

CURRENT LEAD SCORE: {lead_score}
Reply naturally as Arya. Keep it concise — this is WhatsApp.
"""
        }
    ]

    # Add conversation history (last 6 messages for context window)
    for msg in conversation_history[-6:]:
        messages.append(msg)

    # Add current user message
    messages.append({
        "role": "user",
        "content": user_message
    })

    # Step 4: Call Groq
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=300,        # keep WhatsApp replies short
        temperature=0.4,       # low = consistent, professional tone
    )

    reply_text = response.choices[0].message.content.strip()

    # Step 5: Check escalation keywords in reply or message
    escalate = any(word in user_message.lower() for word in [
        "pro forma", "place order", "invoice", "speak to",
        "talk to", "manager", "lc", "letter of credit"
    ]) or lead_score == "HOT"

    return {
        "reply": reply_text,
        "lead_score": lead_score,
        "escalate": escalate,
        "context_used": [m["doc"] for m in
                         collection.query(
                             query_texts=[user_message],
                             n_results=TOP_K_CHUNKS
                         )["metadatas"][0]]
    }


# ─────────────────────────────────────────────
# SIMPLE TERMINAL DEMO
# (Replace this with FastAPI webhook later)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  IndoGulf Trading — Arya AI Agent (Demo)")
    print("="*50)
    print("Type your message as if you're a WhatsApp lead.")
    print("Type 'quit' to exit.\n")

    conversation_history = []

    while True:
        user_input = input("Lead: ").strip()

        if user_input.lower() in ["quit", "exit", "q"]:
            print("Session ended.")
            break

        if not user_input:
            continue

        print("\nArya: thinking...\n")

        result = generate_reply(
            user_message=user_input,
            conversation_history=conversation_history,
        )

        # Print the reply
        print(f"Arya: {result['reply']}")

        # Print metadata (for demo visibility)
        print(f"\n  📊 Lead Score : {result['lead_score']}")
        print(f"  🚨 Escalate   : {'YES — notify human team' if result['escalate'] else 'No'}")
        print(f"  📚 KB Sources : {', '.join(result['context_used'])}")
        print()

        # Update conversation history
        conversation_history.append({"role": "user", "content": user_input})
        conversation_history.append({"role": "assistant", "content": result["reply"]})