from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessDocumentationRequest(BaseModel):
    url: HttpUrl
    chat_id: str


class ProcessDocumentationResponse(BaseModel):
    chat_id: str
    status: ProcessingStatus
    message: str


class ProcessingStatusResponse(BaseModel):
    chat_id: str
    status: ProcessingStatus
    progress: int
    error_message: Optional[str] = None


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    chat_id: str
    response: str
    sources: List[str] = []
    metadata: Optional[Dict[str, Any]] = None


class ChatHistoryResponse(BaseModel):
    chat_id: str
    messages: List[Dict[str, Any]]


class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None 