import os
import getpass
import json
import textwrap
from typing import List, Dict, Any
from typing_extensions import TypedDict
import pyodbc
from ollama import Client
from langchain_community.utilities import SQLDatabase
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from typing_extensions import Annotated
from dotenv import load_dotenv


# print(pyodbc.drivers())

class State(TypedDict):
    question: str
    query: str
    result: str
    answer: str


system_message = """
    Given an input question, create a syntactically correct {dialect} query to
    run to help find the answer. Unless the user specifies in his question a
    specific number of examples they wish to obtain, always limit your query to
    at most {top_k} results. You can order the results by a relevant column to
    return the most interesting examples in the database.

    Never query for all the columns from a specific table, only ask for a the
    few relevant columns given the question.

    Pay attention to use only the column names that you can see in the schema
    description. Be careful to not query for columns that do not exist. Also,
    pay attention to which column is in which table.

    Only use the following tables:
    {table_info}
"""

user_prompt = "Question: {input}"

query_prompt_template = ChatPromptTemplate(
    [("system", system_message), ("user", user_prompt)]
)
class QueryOutput(TypedDict):
    """Generated SQL query."""
    query: Annotated[str, ..., "Syntactically valid SQL query."]


def write_query(state: State):
    """Generate SQL query to fetch information."""
    prompt = query_prompt_template.invoke(
        {
            "dialect": db.dialect,
            "top_k": 10,
            "table_info": db.get_table_info(),
            "input": state["question"],
        }
    )
    structured_llm = llm.with_structured_output(QueryOutput)
    result = structured_llm.invoke(prompt)
    return {"query": result["query"]}


load_dotenv()

# ---------- Config ----------
# SQL Server connection — set in .env or environment
SQL_SERVER = os.getenv("SQL_SERVER", "localhost")
SQL_DATABASE = os.getenv("SQL_DATABASE", "rag_chatbot_ollama")
SQL_USERNAME = os.getenv("SQL_USERNAME", "sa")
SQL_PASSWORD = os.getenv("SQL_PASSWORD", "pakistan")
SQL_DRIVER = os.getenv("SQL_DRIVER", "{ODBC Driver 18 for SQL Server}")
if not os.environ.get("OPENAI_API_KEY"):
  os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter API key for OpenAI: ")

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

"""
conn = get_sql_connection()
cursor = conn.cursor()
cursor.execute("SELECT [Id],[Name],[SSN],[BioData],[Education],[Work] FROM Person")
for row in cursor.fetchall():
    print(row[0], row[1], row[2], row[3])
"""

db_uri = "mssql+pyodbc://sa:pakistan@DESKTOP-HOME\\HOME/rag_chatbot_ollama?driver=ODBC+Driver+17+for+SQL+Server"

db = SQLDatabase.from_uri(db_uri)

# print(db.get_table_info())
print(db.dialect)
print(db.get_usable_table_names())

# llm = init_chat_model("llama3.2:latest", model_provider="ollama")
llm = init_chat_model("gpt-4o-mini", model_provider="openai")

for message in query_prompt_template.messages:
    message.pretty_print()
    
write_query({"question": "How many Perons are there?"})