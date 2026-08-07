"""
IndoGulf Trading — Knowledge Base Loader
=========================================
Loads all 6 knowledge base documents into ChromaDB.
Uses nomic-embed-text via Ollama (local, tiny, 274MB only).
No heavy LLM needed here — Groq handles that separately.

Requirements:
    pip install chromadb
    Ollama running with nomic-embed-text pulled

Run:
    python load_knowledge_base.py
"""

import os
import re
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

KB_FOLDER   = "./kb"
DB_FOLDER   = "./indogulf_db"
COLLECTION  = "indogulf_trading"
OLLAMA_URL  = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"   # tiny 274MB — only this, no heavy LLM

# ─────────────────────────────────────────────
# STEP 1: CONNECT TO CHROMADB
# ─────────────────────────────────────────────

print("\n📦 Connecting to ChromaDB...")

client = chromadb.PersistentClient(path=DB_FOLDER)

embedding_fn = OllamaEmbeddingFunction(
    url=OLLAMA_URL,
    model_name=EMBED_MODEL,
)

# Delete existing collection if reloading fresh
try:
    client.delete_collection(name=COLLECTION)
    print("   ♻️  Cleared existing collection")
except:
    pass

collection = client.get_or_create_collection(
    name=COLLECTION,
    embedding_function=embedding_fn,
    metadata={"description": "IndoGulf Trading knowledge base"}
)

print(f"✅ Collection '{COLLECTION}' ready")


# ─────────────────────────────────────────────
# STEP 2: CHUNKING
# ─────────────────────────────────────────────

def chunk_by_headers(text: str, doc_name: str) -> list[dict]:
    """
    Split markdown document into chunks at ## headers.
    Keeps related information together — smarter than
    splitting by character count.
    """
    chunks = []
    sections = re.split(r'\n(?=## )', text)

    for section in sections:
        section = section.strip()
        if not section or len(section) < 50:
            continue
        first_line = section.split('\n')[0].strip()
        chunks.append({
            "text": section,
            "doc": doc_name,
            "section": first_line
        })

    return chunks


# ─────────────────────────────────────────────
# STEP 3: READ AND CHUNK ALL DOCUMENTS
# ─────────────────────────────────────────────

print("\n📄 Reading knowledge base documents...")

SKIP_FILES = ["00_system_prompt.md"]  # system prompt is NOT for RAG
all_chunks = []

for filename in sorted(os.listdir(KB_FOLDER)):
    if not filename.endswith(".md"):
        continue
    if filename in SKIP_FILES:
        print(f"   ⏭️  Skipping {filename} (used directly as system prompt)")
        continue

    filepath = os.path.join(KB_FOLDER, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    chunks = chunk_by_headers(text, doc_name=filename)
    all_chunks.extend(chunks)
    print(f"   ✅ {filename} → {len(chunks)} chunks")

print(f"\n📊 Total: {len(all_chunks)} chunks to embed")


# ─────────────────────────────────────────────
# STEP 4: EMBED AND STORE
# ─────────────────────────────────────────────

print("\n🔢 Embedding chunks via nomic-embed-text...")
print("   Make sure Ollama is running (ollama serve)\n")

documents = [c["text"] for c in all_chunks]
metadatas = [{"doc": c["doc"], "section": c["section"]} for c in all_chunks]
ids       = [f"chunk_{i:04d}" for i in range(len(all_chunks))]

collection.add(
    documents=documents,
    metadatas=metadatas,
    ids=ids
)

print(f"✅ {len(documents)} chunks stored in ChromaDB")
print(f"📁 Saved to: {os.path.abspath(DB_FOLDER)}")


# ─────────────────────────────────────────────
# STEP 5: QUICK VERIFICATION
# ─────────────────────────────────────────────

print("\n🧪 Testing a few queries...\n")

tests = [
    "What is the MOQ for cashew kernels?",
    "Do you export to Dubai?",
    "What are payment terms for new buyers?",
]

for q in tests:
    results = collection.query(query_texts=[q], n_results=1)
    doc     = results["metadatas"][0][0]["doc"]
    section = results["metadatas"][0][0]["section"]
    preview = results["documents"][0][0][:100].replace('\n', ' ')
    print(f"   Q: {q}")
    print(f"   → [{doc}] {section}")
    print(f"   → {preview}...\n")

print("="*50)
print("✅ Knowledge base ready! Run agent.py next.")
print("="*50)