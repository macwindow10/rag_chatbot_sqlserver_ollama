"""
RAG Chatbot over SQL Server using Ollama + ChromaDB.

- Expects Ollama running locally (default http://localhost:11434) or set OLLAMA_HOST.
- Pull an embedding model and an instruct/LLM model into Ollama beforehand (e.g. using `ollama pull ...`).
- Masks SSNs before embedding (PII safety).
"""

import os
import json
import textwrap
from typing import List, Dict, Any

import pyodbc
from ollama import Client
# import chromadb
from chromadb import PersistentClient
from chromadb.config import Settings
from dotenv import load_dotenv


# print(pyodbc.drivers())


load_dotenv()

# ---------- Config ----------
# SQL Server connection — set in .env or environment
SQL_SERVER = os.getenv("SQL_SERVER", "localhost")
SQL_DATABASE = os.getenv("SQL_DATABASE", "rag_chatbot_ollama")
SQL_USERNAME = os.getenv("SQL_USERNAME", "sa")
SQL_PASSWORD = os.getenv("SQL_PASSWORD", "pakistan")
SQL_DRIVER = os.getenv("SQL_DRIVER", "{ODBC Driver 18 for SQL Server}")

# Ollama host & models
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
# Embedding model name available in your Ollama installation (example names; change if needed)
EMBED_MODEL = os.getenv("EMBED_MODEL", "mxbai-embed-large:latest")   # pick an embed model you pulled
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:latest")                 # pick an instruct/LLM model

# Chromadb client settings (persist locally)
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

# retrieval config
TOP_K = int(os.getenv("TOP_K", "3"))

# ---------- Utilities ----------
def get_sql_connection():
    conn_str = (
        f"DRIVER={SQL_DRIVER};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
    )
    if SQL_USERNAME:
        conn_str += f"UID={SQL_USERNAME};PWD={SQL_PASSWORD};"
    else:
        conn_str += "Trusted_Connection=yes;"
    return pyodbc.connect(conn_str, autocommit=True)

def mask_ssn(ssn: str) -> str:
    """Simple SSN masking: keep last 4 digits only, rest replaced with X's.
       If format unknown, just return '[REDACTED]'."""
    if not ssn:
        return ""
    digits = "".join(ch for ch in ssn if ch.isdigit())
    if len(digits) >= 4:
        return "XXX-XX-" + digits[-4:]
    return "[REDACTED]"

def row_to_person_doc(row: pyodbc.Row) -> Dict[str, Any]:
    """Convert Person row to a textual document and metadata."""
    meta = {"table": "Person", "id": str(row.Id)}
    name = getattr(row, "Name", "")
    ssn = mask_ssn(getattr(row, "SSN", "") or "")
    bio = getattr(row, "BioData", "") 
    # To be robust, try typical column names
    # Compose a short document
    doc_text = textwrap.dedent(f"""
        Person:
        Id: {row.Id}
        Name: {name}
        SSN: {ssn}
        Bio: {bio}
        Education: {getattr(row, 'Education', '')}
        Work: {getattr(row, 'Work', '')}
    """).strip()
    return {"id": meta["id"], "text": doc_text, "meta": meta}

def row_to_event_doc(row: pyodbc.Row) -> Dict[str, Any]:
    meta = {"table": "Event", "id": str(row.Id)}
    # handle possible column names for Persons Involved variations
    persons_involved = getattr(row, "Persons Involved", None) or getattr(row, "PersonsInvolved", None) or getattr(row, "PersonsInvolvedList", None) or getattr(row, "Persons_Involved", "")
    doc_text = textwrap.dedent(f"""
        Event:
        Id: {row.Id}
        Subject: {getattr(row, 'Subject', '')}
        Date: {getattr(row, 'Date', '')}
        Source: {getattr(row, 'Source', '')}
        Latitude: {getattr(row, 'Latitude', '')}
        Longitude: {getattr(row, 'Longitude', '')}
        Address: {getattr(row, 'Address', '')}
        Description: {getattr(row, 'Description', '')}
        Persons Involved: {persons_involved}
    """).strip()
    # print(doc_text)
    return {"id": meta["id"], "text": doc_text, "meta": meta}

# ---------- DB ingestion ----------
def load_and_index_all():
    """
    1) Read Person and Event tables
    2) Create embeddings via Ollama
    3) Add to Chroma collection
    """
    # init Ollama client
    ollama_client = Client(host=OLLAMA_HOST)

    # init chroma
    chroma_client = PersistentClient(path=CHROMA_PERSIST_DIR)
    collection_name = "sql_docs"
    try:
        collection = chroma_client.get_collection(collection_name)
    except Exception:
        collection = chroma_client.create_collection(name=collection_name)

    # Connect to SQL Server
    conn = get_sql_connection()
    cursor = conn.cursor()

    docs_texts = []
    docs_ids = []
    docs_metadatas = []

    # --- Persons ---
    cursor.execute("SELECT [Id],[Name],[SSN],[BioData],[Education],[Work] FROM Person")
    for row in cursor.fetchall():
        doc = row_to_person_doc(row)
        docs_ids.append(f"Person:{doc['id']}")
        docs_texts.append(doc['text'])
        docs_metadatas.append({"table": "Person", "row_id": doc['id']})

    # --- Events ---
    cursor.execute("SELECT e.Id,e.Subject,e.Date,e.Source,e.Latitude,e.Longitude,e.Address,e.Description, STRING_AGG(p.Name, ', ') AS PersonsInvolved \
        FROM Event e LEFT JOIN EventPerson ep ON e.Id = ep.EventId LEFT JOIN Person p ON ep.PersonId=p.Id \
        GROUP BY e.Id,e.Subject,e.Date,e.Source,e.Latitude,e.Longitude,e.Address,e.Description;")
    for row in cursor.fetchall():
        doc = row_to_event_doc(row)
        docs_ids.append(f"Event:{doc['id']}")
        docs_texts.append(doc['text'])
        docs_metadatas.append({"table": "Event", "row_id": doc['id']})

    print(f"[+] Fetched {len(docs_texts)} documents from SQL Server")

    # Generate embeddings in batches using Ollama embedding endpoint
    # Ollama's python client exposes a .embeddings(...) function in examples
    # We'll call it iteratively in small batches to avoid timeouts.
    
    # BATCH = 32
    BATCH = 1
    all_embeddings = []
    for i in range(0, len(docs_texts), BATCH):
        batch_texts = [str(text).replace('\r', ' ').replace('\n', ' ') for text in docs_texts[i:i+BATCH]]
        # print(batch_texts)
        # Ensure all items are strings and no newlines
        batch_texts_clean = [str(text).replace('\n', ' ').strip() for text in batch_texts]
        # print('batch_texts_clean', len(batch_texts_clean))
        print(batch_texts_clean[0])
        # Defensive: if only one doc, still pass as list        
        if len(batch_texts_clean) == 1:
            resp = ollama_client.embeddings(model=EMBED_MODEL, prompt=batch_texts_clean[0])
        else:
            resp = ollama_client.embeddings(model=EMBED_MODEL, prompt=batch_texts_clean)
        # Response shape depends on Ollama client version: normalize
        # If resp is list/dict, extract 'embedding' fields accordingly
        # We'll accept resp to be either a list of dicts or a dict with 'embedding' for single item.
        if isinstance(resp, dict) and "embedding" in resp:
            all_embeddings.append(resp["embedding"])
        else:
            # try to flatten
            for item in resp:
                if isinstance(item, dict) and "embedding" in item:
                    all_embeddings.append(item["embedding"])
                else:
                    # sometimes response is direct list of list floats
                    all_embeddings.append(item)

    print(f"[+] Generated {len(all_embeddings)} embeddings")

    # Add to Chroma
    # We may want to upsert to update existing docs
    embeddings2 = [e[1] for e in all_embeddings]
    #for e in all_embeddings:
    #    print(e[1])
    collection.add(
        ids=docs_ids,
        documents=docs_texts,
        metadatas=docs_metadatas,
        embeddings=embeddings2
    )
    # chroma_client.persist()
    print("[+] Indexed documents into ChromaDB")

# ---------- Retrieval + answer generation ----------
def retrieve_context(query: str, top_k: int = TOP_K):
    """Embed query and query ChromaDB to get top_k documents and metadata."""
    ollama_client = Client(host=OLLAMA_HOST)
    chroma_client = PersistentClient(path=CHROMA_PERSIST_DIR)
    collection = chroma_client.get_collection("sql_docs")
    print(f"collection length: {collection.count()}")
    
    q_resp = ollama_client.embeddings(model=EMBED_MODEL, prompt=query)
    if isinstance(q_resp, dict) and "embedding" in q_resp:
        q_emb = q_resp["embedding"]
        # print("q_emb:1")
    elif isinstance(q_resp, list) and len(q_resp) > 0 and isinstance(q_resp[0], dict) and "embedding" in q_resp[0]:
        q_emb = q_resp[0]["embedding"]
        # print("q_emb:2")
    else:
        # fallback: assume direct list returned
        q_emb = q_resp["embedding"]
        # print("q_emb:3")

    # print("q_emb:", q_emb)
    
    results = collection.query(query_embeddings=[q_emb], n_results=top_k, include=["documents", "metadatas", "distances"])
    docs = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    retrieved = []
    for doc, meta, dist in zip(docs, metadatas, distances):
        retrieved.append({"doc": doc, "meta": meta, "distance": dist})
    return retrieved

def generate_answer(query: str, retrieved_docs: List[Dict[str,Any]]):
    """
    Build a prompt combining retrieved context + query and call Ollama LLM.
    Instruct model to answer only using provided context.
    """
    ollama_client = Client(host=OLLAMA_HOST)

    # Build context block — we include metadata to be explicit
    context_blocks = []
    for i, r in enumerate(retrieved_docs, start=1):
        context_blocks.append(f"--- CONTEXT {i} (table={r['meta'].get('table')}, row_id={r['meta'].get('row_id')}) ---\n{r['doc']}")
    context_text = "\n\n".join(context_blocks)

    system_prompt = textwrap.dedent(f"""
        You are a helpful assistant answering questions about events and people.
        ONLY use the information provided in the CONTEXT blocks below (do not hallucinate).
        If the answer is not present in the context, say you don't have enough information.
        Keep answers concise and list facts (do not invent details).
    """).strip()

    user_prompt = textwrap.dedent(f"""
        CONTEXT:
        {context_text}

        QUESTION:
        {query}

        INSTRUCTIONS:
        - Answer using only facts available in the CONTEXT.
        - If multiple matching items exist, present a short bulleted list with identifying fields (e.g., Event Id, Subject, Date, Location).
        - For people, show Name, Profession, and Id if available.
    """).strip()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # Call Ollama chat/generate
    # Use 'chat' interface if model supports it (gemma3/gpt-style). Otherwise use generate with prompt.
    try:
        resp = ollama_client.chat(model=LLM_MODEL, messages=messages)
        # response format may be { 'choices': [{'message': {'content': '...'}}]} or similar
        if isinstance(resp, dict):
            if "choices" in resp and resp["choices"]:
                content = resp["choices"][0].get("message", {}).get("content") or resp["choices"][0].get("text")
            else:
                content = resp.get("text") or json.dumps(resp)
        else:
            content = str(resp)
    except Exception:
        # fallback to generate with concatenated prompt
        full_prompt = system_prompt + "\n\n" + user_prompt
        gen = ollama_client.generate(model=LLM_MODEL, prompt=full_prompt)
        # extract reasonably
        if isinstance(gen, dict) and "text" in gen:
            content = gen["text"]
        else:
            content = str(gen)

    return content

# ---------- Example queries ----------
EXAMPLE_QUERIES = [
    "What events involved John Smith in 2023?",
    "List people whose profession is Doctor and who attended events on Climate Change.",
    "List events happened in Washington DC during Feb 2023 to June 2023."
]

def run_examples():
    print("[*] Retrieving answers for example queries:")
    for q in EXAMPLE_QUERIES:
        print("\n-----")
        print("Q:", q)
        retrieved = retrieve_context(q)
        print(f"[+] Retrieved {len(retrieved)} documents (top {TOP_K})")
        ans = generate_answer(q, retrieved)
        print("\nAnswer:\n", ans)

# ---------- CLI ----------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG Chatbot over SQL Server using Ollama & ChromaDB")
    parser.add_argument("--index", action="store_true", help="Index SQL Server rows into vector DB (run first)")
    parser.add_argument("--ask", type=str, help="Ask a natural language question")
    parser.add_argument("--examples", action="store_true", help="Run built-in example queries")
    args = parser.parse_args()

    if args.index:
        load_and_index_all()
    elif args.ask:
        retrieved = retrieve_context(args.ask)
        print(f"[+] Retrieved {len(retrieved)} documents")
        ans = generate_answer(args.ask, retrieved)
        print("\n--- Answer ---\n")
        print(ans)
    elif args.examples:
        run_examples()
    else:
        parser.print_help()
