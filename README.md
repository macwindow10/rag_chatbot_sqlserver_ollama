# 🤖 RAG Chatbot over SQL Server using Ollama & ChromaDB

This project implements a Retrieval-Augmented Generation (RAG) chatbot that answers questions about people and events stored in a SQL Server database.

It uses:

- 🦙 **Ollama** for local LLM and embedding models
- 🗄️ **SQL Server** for data storage
- 🧠 **ChromaDB** for vector storage and retrieval

## ✨ Features

- 🗄️ Connects to SQL Server and ingests data from `Person` and `Event` tables
- 🛡️ Masks SSNs for privacy before embedding
- 🦙 Generates embeddings using Ollama's embedding models
- 🧠 Stores and retrieves document embeddings with ChromaDB
- 💬 Answers natural language questions using context retrieved from the database
- 🖥️ CLI for indexing, asking questions, and running example queries

## 📦 Requirements

- 🐍 Python 3.8+
- 🗄️ SQL Server (local or remote)
- 🦙 Ollama (local LLM/embedding server)
- 🧠 ChromaDB
- 📦 Required Python packages: `pyodbc`, `ollama`, `chromadb`, `python-dotenv`

## ⚡ Setup

1. 🛠️ **Clone the repository**
2. 📦 **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```
3. ⚙️ **Configure environment variables**:
   - Create a `.env` file in the project root with:
     ```env
     SQL_SERVER=localhost
     SQL_DATABASE=rag_chatbot_ollama
     SQL_USERNAME=sa
     SQL_PASSWORD=your_password
     SQL_DRIVER={ODBC Driver 18 for SQL Server}
     OLLAMA_HOST=http://localhost:11434
     EMBED_MODEL=mxbai-embed-large:latest
     LLM_MODEL=llama3.2:latest
     CHROMA_PERSIST_DIR=./chroma_db
     TOP_K=6
     ```
   - Adjust values as needed for your environment.
4. 🦙 **Start Ollama** and pull required models:
   ```powershell
   ollama pull mxbai-embed-large:latest
   ollama pull llama3.2:latest
   ```
5. 🗄️ **Prepare your SQL Server database** with `Person` and `Event` tables. See `insert_queries.sql` for example schema and seed data.

## 🚀 Usage

### 📥 Index Data

```powershell
python rag_chatbot_sqlserver_ollama.py --index
```

### ❓ Ask a Question

```powershell
python rag_chatbot_sqlserver_ollama.py --ask "What events involved John Smith in 2023?"
```

### 🧪 Run Example Queries

```powershell
python rag_chatbot_sqlserver_ollama.py --examples
```

## 📁 File Structure

- `rag_chatbot_sqlserver_ollama.py` — 🐍 Main script
- `insert_queries.sql` — 🗄️ Example SQL seed data
- `chroma_db/` — 🧠 ChromaDB persistent storage
- `db_seeder/main.py` — 🌱 Optional DB seeder script
- `chatgpt_prompt/` — 💬 (Optional) prompt templates

## 🛠️ Customization

- 🔄 Change embedding/LLM models in `.env` as needed
- 📝 Adjust SQL queries for your schema
- 🧩 Extend document formatting in `row_to_person_doc` and `row_to_event_doc`

## 📄 License

MIT

## 👤 Author

mac.window.10@gmail.com
