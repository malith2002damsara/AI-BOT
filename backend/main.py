import os
import shutil
from typing import TypedDict, Annotated, Sequence, List, Dict, Any
from operator import add as add_messages
import logging
import json

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    AIMessage,
)
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_community.embeddings import JinaEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
import requests

# ---------- Setup logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Load environment variables ----------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
JINA_API_KEY = os.getenv("JINA_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "jina-embeddings-v3")
FRONTEND_URL = os.getenv("FRONTEND_URL", "*")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------- Google Translate using requests ----------
def translate_to_sinhala(text: str) -> str:
    """Translate English text to Sinhala using Google Translate API"""
    try:
        if not text or text.strip() == "":
            return text
        
        if any('\u0D80' <= char <= '\u0DFF' for char in text):
            return text
        
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "en",
            "tl": "si",
            "dt": "t",
            "q": text
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            result = response.json()
            translated_text = ""
            for item in result[0]:
                if item[0]:
                    translated_text += item[0]
            return translated_text
        else:
            return text
            
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return text

def translate_to_english(text: str) -> str:
    """Translate Sinhala text to English using Google Translate API"""
    try:
        if not text or text.strip() == "":
            return text
        
        if not any('\u0D80' <= char <= '\u0DFF' for char in text):
            return text
        
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "si",
            "tl": "en",
            "dt": "t",
            "q": text
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            result = response.json()
            translated_text = ""
            for item in result[0]:
                if item[0]:
                    translated_text += item[0]
            return translated_text
        else:
            return text
            
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return text

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

# ---------- 2. Vectorstore / Retriever ----------
retriever = None

def build_vectorstore(pdf_path: str):
    """PDF එකෙන් vectorstore එක build කරනවා"""
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

# Default PDF එක load කරනවා
_default_pdf = os.path.join(os.path.dirname(__file__), "codeprolk.pdf")
if os.path.exists(_default_pdf):
    build_vectorstore(_default_pdf)

# ---------- Define Tools with proper names ----------
@tool
def retriever_tool(query: str) -> str:
    """Use this tool to search and retrieve information from the uploaded PDF document. Input should be a search query string."""
    if retriever is None:
        return "කරුණාකර මුලින්ම PDF එකක් upload කරන්න."
    try:
        # Translate Sinhala query to English if needed
        if any('\u0D80' <= char <= '\u0DFF' for char in query):
            query = translate_to_english(query)
        
        docs = retriever.invoke(query)
        if not docs:
            return "අදාළ තොරතුරු කිසිවක් හමු නොවුණා."
        
        results = [f"ලේඛනය {i+1}:\n{doc.page_content}" for i, doc in enumerate(docs)]
        result_text = "\n\n".join(results)
        
        # Translate results to Sinhala
        return translate_to_sinhala(result_text)
    except Exception as e:
        logger.error(f"Error in retriever_tool: {str(e)}")
        return f"ලේඛනයෙන් තොරතුරු ලබා ගැනීමේ දෝෂයක්: {str(e)}"

@tool
def wikipedia_tool(query: str) -> str:
    """Use this tool to search Wikipedia for general knowledge questions. Input should be a search query string."""
    try:
        import wikipedia
        wikipedia.set_lang("en")
        
        # Translate Sinhala query to English if needed
        if any('\u0D80' <= char <= '\u0DFF' for char in query):
            query = translate_to_english(query)
        
        # Search Wikipedia
        search_results = wikipedia.search(query)
        if not search_results:
            return f"'{query}' සඳහා Wikipedia ලිපි කිසිවක් හමු නොවුණා."
        
        # Get summary of first result
        try:
            page = wikipedia.page(search_results[0], auto_suggest=False)
            summary = page.summary[:4000]
            result = f"පිටුව: {page.title}\nසාරාංශය: {summary}"
            return translate_to_sinhala(result)
            
        except wikipedia.exceptions.DisambiguationError as e:
            try:
                page = wikipedia.page(e.options[0], auto_suggest=False)
                summary = page.summary[:4000]
                result = f"පිටුව: {page.title}\nසාරාංශය: {summary}"
                return translate_to_sinhala(result)
            except:
                return f"'{query}' සඳහා Wikipedia ලිපි කිහිපයක් හමු වුණා. කරුණාකර වඩාත් නිශ්චිතව සඳහන් කරන්න."
                
        except wikipedia.exceptions.PageError:
            return f"'{query}' සඳහා Wikipedia පිටුවක් හමු නොවුණා."
        
    except requests.exceptions.Timeout:
        return "Wikipedia සම්බන්ධතාවය කල් ඉකුත් වුණා. කරුණාකර නැවත උත්සාහ කරන්න."
    except requests.exceptions.ConnectionError:
        return "Wikipedia සම්බන්ධ කර ගැනීමේ ජාල දෝෂයක්. කරුණාකර ඔබගේ අන්තර්ජාල සම්බන්ධතාවය පරීක්ෂා කරන්න."
    except Exception as e:
        logger.error(f"Wikipedia error for query '{query}': {str(e)}")
        return f"Wikipedia භාවිතා කිරීමේ දෝෂයක්: {str(e)}"

# Rename the tool to avoid conflict
wikipedia_tool.name = "wikipedia_search"

tools = [retriever_tool, wikipedia_tool]
tools_dict = {t.name: t for t in tools}

# ---------- 3. LangGraph Agent ----------
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    language: str  # Add language preference to state

system_prompt = """
You are an intelligent AI assistant who answers questions about the uploaded PDF document.

Available tools:
1. retriever_tool - Use this to search the uploaded PDF document
2. wikipedia_search - Use this to search Wikipedia for general knowledge

When using tools:
- For retriever_tool: pass the search query as 'query' parameter
- For wikipedia_search: pass the search query as 'query' parameter

Example tool calls:
- {"name": "retriever_tool", "arguments": {"query": "your search term"}}
- {"name": "wikipedia_search", "arguments": {"query": "your search term"}}

First, try to answer using the PDF document. If no relevant information is found, use Wikipedia.
"""

def should_continue(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    
    # Check if the last message has tool calls
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return True
    
    # For AIMessage, check if it has tool_calls attribute
    if isinstance(last_message, AIMessage) and hasattr(last_message, 'tool_calls'):
        return len(last_message.tool_calls) > 0
    
    return False

def call_llm(state: AgentState) -> AgentState:
    """Call the LLM with tools"""
    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Invoke LLM
    response = llm_with_tools.invoke(messages)
    
    # Get language preference from state
    language = state.get("language", "sinhala")
    
    # Translate response based on language preference
    if hasattr(response, 'content') and response.content:
        if language.lower() == "sinhala":
            # If content is in English, translate to Sinhala
            if not any('\u0D80' <= char <= '\u0DFF' for char in response.content):
                response.content = translate_to_sinhala(response.content)
        else:  # English
            # If content is in Sinhala, translate to English
            if any('\u0D80' <= char <= '\u0DFF' for char in response.content):
                response.content = translate_to_english(response.content)
    
    return {"messages": [response], "language": language}

def take_action(state: AgentState) -> AgentState:
    """Execute tool calls"""
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_calls = []
    if hasattr(last_message, 'tool_calls'):
        tool_calls = last_message.tool_calls
    
    if not tool_calls:
        return {"messages": []}
    
    results = []
    for tool_call in tool_calls:
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})
        tool_id = tool_call.get("id", "")
        
        if tool_name not in tools_dict:
            result = f"වැරදි මෙවලම් නමක්: {tool_name}"
        else:
            try:
                # Get the tool and invoke it
                tool_obj = tools_dict[tool_name]
                
                # Extract query from args
                if "query" in tool_args:
                    query = tool_args["query"]
                elif "input" in tool_args:
                    query = tool_args["input"]
                else:
                    # Use the first argument
                    args_list = list(tool_args.values())
                    if args_list:
                        query = args_list[0]
                    else:
                        result = "මෙවලමට තර්ක කිසිවක් සපයා නැත."
                        results.append(ToolMessage(
                            tool_call_id=tool_id,
                            name=tool_name,
                            content=str(result)
                        ))
                        continue
                
                # Invoke the tool
                result = tool_obj.invoke(query)
                
            except Exception as e:
                logger.error(f"Error in take_action for tool {tool_name}: {str(e)}")
                result = f"මෙවලම ක්‍රියාත්මක කිරීමේ දෝෂය: {str(e)}"
        
        # Create ToolMessage
        tool_message = ToolMessage(
            tool_call_id=tool_id,
            name=tool_name,
            content=str(result)
        )
        results.append(tool_message)
    
    return {"messages": results}

# Build the workflow
workflow = StateGraph(AgentState)
workflow.add_node("llm", call_llm)
workflow.add_node("retriever_agent", take_action)
workflow.add_edge(START, "llm")
workflow.add_conditional_edges("llm", should_continue, {True: "retriever_agent", False: END})
workflow.add_edge("retriever_agent", "llm")

# Compile the graph
app_graph = workflow.compile()

# ---------- 4. FastAPI App ----------
app = FastAPI(title="RAG Agent API - Sinhala")

# Configure CORS with more permissive settings for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    language: str = "sinhala"  # Default to Sinhala

class ChatResponse(BaseModel):
    reply: str

@app.get("/")
def health_check():
    return {
        "status": "ok", 
        "message": "RAG Agent API is running - Sinhala Support",
        "pdf_loaded": retriever is not None
    }

@app.get("/test")
def test_endpoint():
    return {"message": "Backend is working!"}

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="PDF file එකක් පමණක් upload කළ හැකියි")

        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            build_vectorstore(file_path)
        except Exception as e:
            logger.error(f"PDF processing error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"PDF සැකසීමේ දෝෂයක්: {str(e)}")

        return {"status": "ok", "filename": file.filename, "message": "PDF එක සාර්ථකව සැකසුණා"}
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        # Invoke the graph with language preference
        result = app_graph.invoke({
            "messages": [HumanMessage(content=req.message)],
            "language": req.language
        })
        
        # Extract the final response
        if result["messages"] and len(result["messages"]) > 0:
            last_message = result["messages"][-1]
            reply = last_message.content if hasattr(last_message, 'content') else str(last_message)
            
            # Ensure response matches language preference
            if req.language.lower() == "sinhala":
                if not any('\u0D80' <= char <= '\u0DFF' for char in reply):
                    reply = translate_to_sinhala(reply)
            else:  # English
                if any('\u0D80' <= char <= '\u0DFF' for char in reply):
                    reply = translate_to_english(reply)
        else:
            reply = "පිළිතුරක් ජනනය කළ නොහැකි වුණා." if req.language.lower() == "sinhala" else "Unable to generate response."
        
        return {"reply": reply}
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        error_msg = f"ඔබගේ ඉල්ලීම සැකසීමේ දෝෂයක්: {str(e)}" if req.language.lower() == "sinhala" else f"Error processing your request: {str(e)}"
        return {"reply": error_msg}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)