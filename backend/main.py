import os
import shutil
from typing import TypedDict, Annotated, Sequence
from operator import add as add_messages

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_community.embeddings import JinaEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

# ---------- Load environment variables ----------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
JINA_API_KEY = os.getenv("JINA_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "jina-embeddings-v3")
FRONTEND_URL = os.getenv("FRONTEND_URL", "*")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------- 1. LLM & Embeddings ----------
llm = ChatGroq(
    model=LLM_MODEL,
    temperature=0,
    api_key=GROQ_API_KEY,
)

embeddings = JinaEmbeddings(
    model=EMBEDDING_MODEL,
    jina_api_key=JINA_API_KEY,
)

# ---------- 2. Vectorstore / Retriever (rebuilt when a PDF is uploaded) ----------
retriever = None  # PDF upload wenakam None


def build_vectorstore(pdf_path: str):
    """Given PDF path eka, vectorstore eka rebuild karala global retriever eka set karanawa."""
    global retriever

    pdf_loader = PyPDFLoader(pdf_path)
    pages = pdf_loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    pages_split = text_splitter.split_documents(pages)

    vectorstore = Chroma.from_documents(
        documents=pages_split,
        embedding=embeddings,
        collection_name="data",
    )

    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})


# App start wenakota default PDF ekak thiyenawa nam eka load karanawa (optional)
_default_pdf = os.path.join(os.path.dirname(__file__), "codeprolk.pdf")
if os.path.exists(_default_pdf):
    build_vectorstore(_default_pdf)


@tool
def retriever_tool(query: str) -> str:
    """This tool searches and returns information from the uploaded PDF document."""
    if retriever is None:
        return "Document ekak upload karala na. Karunakara mulinma PDF ekak upload karanna."
    docs = retriever.invoke(query)
    if not docs:
        return "I found no relevant information"
    results = [f"Document {i+1}:\n{doc.page_content}" for i, doc in enumerate(docs)]
    return "\n\n".join(results)


wikipedia_tool = WikipediaQueryRun(
    api_wrapper=WikipediaAPIWrapper(top_k_results=3, doc_content_chars_max=4000)
)

tools = [retriever_tool, wikipedia_tool]
llm_with_tools = llm.bind_tools(tools)
tools_dict = {t.name: t for t in tools}


# ---------- 3. LangGraph Agent ----------
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


system_prompt = """
You are an intelligent AI assistant who answers questions about the uploaded PDF document.
Use the retriever tool available to answer questions about the given data. You can make multiple calls if needed.
If the retriever has no relevant info, you may use the wikipedia tool for general knowledge questions.
Please always cite the specific parts of the documents you use in your answers.
"""


def should_continue(state: AgentState):
    result = state["messages"][-1]
    return hasattr(result, "tool_calls") and len(result.tool_calls) > 0


def call_llm(state: AgentState) -> AgentState:
    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    message = llm_with_tools.invoke(messages)
    return {"messages": [message]}


def take_action(state: AgentState) -> AgentState:
    tool_calls = state["messages"][-1].tool_calls
    results = []
    for t in tool_calls:
        if t["name"] not in tools_dict:
            result = "Incorrect Tool Name, Please Retry and Select tool from List of Available tools."
        else:
            result = tools_dict[t["name"]].invoke(t["args"].get("query", ""))
        results.append(ToolMessage(tool_call_id=t["id"], name=t["name"], content=str(result)))
    return {"messages": results}


workflow = StateGraph(AgentState)
workflow.add_node("llm", call_llm)
workflow.add_node("retriever_agent", take_action)
workflow.add_edge(START, "llm")
workflow.add_conditional_edges("llm", should_continue, {True: "retriever_agent", False: END})
workflow.add_edge("retriever_agent", "llm")
app_graph = workflow.compile()


# ---------- 4. FastAPI App ----------
app = FastAPI(title="RAG Agent API")

origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    FRONTEND_URL,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.get("/")
def health_check():
    return {"status": "ok", "message": "RAG Agent API is running", "pdf_loaded": retriever is not None}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="PDF file ekak witharai upload karanna puluwan")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        build_vectorstore(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF process karaddi error ekak awa: {str(e)}")

    return {"status": "ok", "filename": file.filename, "message": "PDF eka process karala iwarai"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    result = app_graph.invoke({"messages": [HumanMessage(content=req.message)]})
    return {"reply": result["messages"][-1].content}