import os
import shutil
from typing import TypedDict, Annotated, Sequence, List, Dict, Any
from operator import add as add_messages
import logging
import json
from datetime import datetime

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
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
import requests
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

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

# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Configure Cloudinary
if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )
    logger.info("Cloudinary configured successfully")
else:
    logger.warning("Cloudinary credentials not found. PDF upload will work without cloud storage.")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Store uploaded PDFs info
uploaded_pdfs = []
current_pdf = None
retriever = None

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

# Use HuggingFace embeddings as fallback if Jina is not available
try:
    from langchain_community.embeddings import JinaEmbeddings
    if JINA_API_KEY:
        embeddings = JinaEmbeddings(
            model=EMBEDDING_MODEL,
            jina_api_key=JINA_API_KEY,
        )
        logger.info("Using Jina embeddings")
    else:
        raise Exception("JINA_API_KEY not found")
except Exception as e:
    logger.warning(f"Jina embeddings not available: {str(e)}. Using HuggingFace embeddings.")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': False}
    )

# ---------- 2. Vectorstore / Retriever ----------
def build_vectorstore(pdf_path: str):
    """Build vectorstore from PDF"""
    global retriever, current_pdf

    try:
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
        current_pdf = pdf_path
        logger.info(f"Vectorstore built successfully from: {pdf_path}")
        return True
    except Exception as e:
        logger.error(f"Error building vectorstore: {str(e)}")
        raise e

def load_pdf_from_cloudinary(public_id: str, file_path: str) -> bool:
    """Load PDF from Cloudinary"""
    try:
        # Get the download URL
        url, options = cloudinary_url(public_id, resource_type="raw", format="pdf")
        
        # Download the PDF
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(response.content)
            logger.info(f"PDF downloaded from Cloudinary: {public_id}")
            return True
        else:
            logger.error(f"Failed to download PDF from Cloudinary: HTTP {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error loading PDF from Cloudinary: {str(e)}")
        return False

# Load default PDF if exists
_default_pdf = os.path.join(os.path.dirname(__file__), "codeprolk.pdf")
if os.path.exists(_default_pdf):
    try:
        build_vectorstore(_default_pdf)
        logger.info("Default PDF loaded successfully")
    except Exception as e:
        logger.error(f"Error loading default PDF: {str(e)}")

# ---------- Define Tools ----------
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
    language: str

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
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return True
    
    if isinstance(last_message, AIMessage) and hasattr(last_message, 'tool_calls'):
        return len(last_message.tool_calls) > 0
    
    return False

def call_llm(state: AgentState) -> AgentState:
    """Call the LLM with tools"""
    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke(messages)
    
    language = state.get("language", "sinhala")
    
    if hasattr(response, 'content') and response.content:
        if language.lower() == "sinhala":
            if not any('\u0D80' <= char <= '\u0DFF' for char in response.content):
                response.content = translate_to_sinhala(response.content)
        else:
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
                tool_obj = tools_dict[tool_name]
                
                if "query" in tool_args:
                    query = tool_args["query"]
                elif "input" in tool_args:
                    query = tool_args["input"]
                else:
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
                
                result = tool_obj.invoke(query)
                
            except Exception as e:
                logger.error(f"Error in take_action for tool {tool_name}: {str(e)}")
                result = f"මෙවලම ක්‍රියාත්මක කිරීමේ දෝෂය: {str(e)}"
        
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    language: str = "sinhala"

class ChatResponse(BaseModel):
    reply: str

@app.get("/")
def health_check():
    return {
        "status": "ok", 
        "message": "RAG Agent API is running - Sinhala Support",
        "pdf_loaded": retriever is not None,
        "pdfs_count": len(uploaded_pdfs)
    }

@app.get("/pdfs")
def get_pdfs():
    return {"pdfs": uploaded_pdfs}

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    global uploaded_pdfs
    
    try:
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="PDF file එකක් පමණක් upload කළ හැකියි")

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        local_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        # Save locally first
        with open(local_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Build vectorstore
        try:
            build_vectorstore(local_path)
        except Exception as e:
            logger.error(f"Vectorstore build error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"PDF processing error: {str(e)}")

        # Upload to Cloudinary if configured
        cloudinary_url_result = None
        public_id = None
        
        if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
            try:
                upload_result = cloudinary.uploader.upload(
                    local_path,
                    resource_type="raw",
                    folder="pdfs",
                    public_id=f"pdf_{timestamp}_{file.filename.replace('.pdf', '')}"
                )
                
                cloudinary_url_result = cloudinary_url(upload_result['public_id'], resource_type="raw", format="pdf")[0]
                public_id = upload_result['public_id']
                logger.info(f"PDF uploaded to Cloudinary: {public_id}")
                
            except Exception as e:
                logger.error(f"Cloudinary upload error: {str(e)}")
                # Still continue even if Cloudinary fails
        
        # Store PDF info
        pdf_info = {
            "id": public_id or f"local_{timestamp}",
            "name": file.filename,
            "cloudinary_url": cloudinary_url_result,
            "public_id": public_id,
            "uploaded_at": datetime.now().isoformat(),
            "local_path": local_path
        }
        uploaded_pdfs.append(pdf_info)

        return {
            "status": "ok", 
            "filename": file.filename, 
            "message": "PDF එක සාර්ථකව සැකසුණා",
            "pdf_info": pdf_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

@app.post("/load-pdf/{public_id}")
def load_pdf(public_id: str):
    """Load a previously uploaded PDF from Cloudinary or local storage"""
    try:
        # Find PDF info
        pdf_info = next((p for p in uploaded_pdfs if p["public_id"] == public_id), None)
        if not pdf_info:
            raise HTTPException(status_code=404, detail="PDF not found")
        
        # Check if local file exists
        if "local_path" in pdf_info and os.path.exists(pdf_info["local_path"]):
            try:
                build_vectorstore(pdf_info["local_path"])
                return {"status": "ok", "message": "PDF loaded successfully from local cache"}
            except Exception as e:
                logger.error(f"Error loading from local cache: {str(e)}")
                # If local loading fails, try downloading again
        
        # If public_id exists and Cloudinary is configured, download from Cloudinary
        if public_id and CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
            try:
                local_path = os.path.join(UPLOAD_DIR, f"loaded_{public_id}.pdf")
                
                if load_pdf_from_cloudinary(public_id, local_path):
                    build_vectorstore(local_path)
                    # Update local_path in pdf_info
                    pdf_info["local_path"] = local_path
                    return {"status": "ok", "message": "PDF loaded successfully from Cloudinary"}
                else:
                    raise Exception("Failed to download PDF from Cloudinary")
                    
            except Exception as e:
                logger.error(f"Cloudinary download error: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to download PDF: {str(e)}")
        else:
            raise HTTPException(status_code=404, detail="PDF file not found locally and Cloudinary not configured")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Load PDF error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading PDF: {str(e)}")

@app.delete("/pdf/{public_id}")
def delete_pdf(public_id: str):
    """Delete a PDF from Cloudinary and local storage"""
    global uploaded_pdfs
    
    try:
        # Find PDF info
        pdf_info = next((p for p in uploaded_pdfs if p["public_id"] == public_id), None)
        
        # Remove from uploaded_pdfs list
        uploaded_pdfs = [p for p in uploaded_pdfs if p["public_id"] != public_id]
        
        # Delete local file if exists
        if pdf_info and "local_path" in pdf_info and os.path.exists(pdf_info["local_path"]):
            try:
                os.remove(pdf_info["local_path"])
                logger.info(f"Local file deleted: {pdf_info['local_path']}")
            except Exception as e:
                logger.error(f"Error deleting local file: {str(e)}")
        
        # Also try to delete any loaded version
        loaded_path = os.path.join(UPLOAD_DIR, f"loaded_{public_id}.pdf")
        if os.path.exists(loaded_path):
            try:
                os.remove(loaded_path)
                logger.info(f"Loaded file deleted: {loaded_path}")
            except Exception as e:
                logger.error(f"Error deleting loaded file: {str(e)}")
        
        # Delete from Cloudinary if configured
        if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
            try:
                result = cloudinary.uploader.destroy(public_id, resource_type="raw")
                logger.info(f"Cloudinary delete result: {result}")
            except Exception as e:
                logger.error(f"Cloudinary delete error: {str(e)}")
        
        return {"status": "ok", "message": "PDF deleted successfully"}
        
    except Exception as e:
        logger.error(f"Delete PDF error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting PDF: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        result = app_graph.invoke({
            "messages": [HumanMessage(content=req.message)],
            "language": req.language
        })
        
        if result["messages"] and len(result["messages"]) > 0:
            last_message = result["messages"][-1]
            reply = last_message.content if hasattr(last_message, 'content') else str(last_message)
            
            if req.language.lower() == "sinhala":
                if not any('\u0D80' <= char <= '\u0DFF' for char in reply):
                    reply = translate_to_sinhala(reply)
            else:
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