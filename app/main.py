import asyncio
import uuid
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.database.database import get_db, create_tables
from app.database.models import ChatSession
from app.models.api import (
    ProcessDocumentationRequest,
    ProcessDocumentationResponse,
    ProcessingStatusResponse,
    ChatMessage,
    ChatResponse,
    ChatHistoryResponse,
    ProcessingStatus
)
from app.services.vector_store import VectorStore
from app.services.document_processor import DocumentProcessor
from app.services.chat_service import ChatService
from app.graph.agent_graph import AgentGraph
from app.config import settings
import logging

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Technical Documentation Agent",
    description="An autonomous agent for analyzing and synthesizing technical documentation",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
vector_store = VectorStore()
agent_graph = AgentGraph(vector_store)
document_processor = DocumentProcessor(vector_store)
chat_service = ChatService(vector_store, agent_graph)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    try:
        # Create database tables
        create_tables()
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Technical Documentation Agent API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/api/v1/process-documentation", response_model=ProcessDocumentationResponse)
async def process_documentation(
    request: ProcessDocumentationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Process documentation from URL"""
    try:
        # Check if chat session already exists
        existing_session = db.query(ChatSession).filter(
            ChatSession.chat_id == request.chat_id
        ).first()
        
        if existing_session:
            raise HTTPException(
                status_code=400,
                detail=f"Chat session with ID {request.chat_id} already exists"
            )
        
        # Create new chat session
        chat_session = ChatSession(
            chat_id=request.chat_id,
            url=str(request.url),
            status="pending"
        )
        db.add(chat_session)
        db.commit()
        
        # Start background processing
        background_tasks.add_task(
            process_documentation_background,
            str(request.url),
            request.chat_id,
            db
        )
        
        return ProcessDocumentationResponse(
            chat_id=request.chat_id,
            status=ProcessingStatus.PROCESSING,
            message="Documentation processing started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting documentation processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_documentation_background(url: str, chat_id: str, db: Session):
    """Background task for processing documentation"""
    try:
        success = await document_processor.process_documentation(url, chat_id, db)
        if not success:
            logger.error(f"Failed to process documentation for chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Error in background processing: {str(e)}")


@app.get("/api/v1/processing-status/{chat_id}", response_model=ProcessingStatusResponse)
async def get_processing_status(chat_id: str, db: Session = Depends(get_db)):
    """Get processing status for a chat session"""
    try:
        session = db.query(ChatSession).filter(
            ChatSession.chat_id == chat_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Chat session with ID {chat_id} not found"
            )
        
        return ProcessingStatusResponse(
            chat_id=chat_id,
            status=ProcessingStatus(session.status),
            progress=session.progress,
            error_message=session.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting processing status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/chat/{chat_id}", response_model=ChatResponse)
async def chat_with_agent(
    chat_id: str,
    message: ChatMessage,
    db: Session = Depends(get_db)
):
    """Chat with the agent"""
    try:
        response = await chat_service.process_message(chat_id, message.message, db)
        return response
        
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/chat-history/{chat_id}", response_model=ChatHistoryResponse)
async def get_chat_history(chat_id: str, db: Session = Depends(get_db)):
    """Get chat history"""
    try:
        response = chat_service.get_chat_history(chat_id, db)
        return response
        
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/chat/{chat_id}")
async def delete_chat(chat_id: str, db: Session = Depends(get_db)):
    """Delete a chat session and all associated data"""
    try:
        success = await chat_service.delete_chat(chat_id, db)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Chat session with ID {chat_id} not found"
            )
        
        return {"message": f"Chat session {chat_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/graph-info")
async def get_graph_info():
    """Get information about the LangGraph structure"""
    try:
        return agent_graph.get_graph_info()
    except Exception as e:
        logger.error(f"Error getting graph info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    ) 