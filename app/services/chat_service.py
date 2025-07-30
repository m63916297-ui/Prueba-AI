from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.database.models import ChatSession, ChatMessage
from app.services.vector_store import VectorStore
from app.graph.agent_graph import AgentGraph
from app.models.api import ChatResponse, ChatHistoryResponse
import logging

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, vector_store: VectorStore, agent_graph: AgentGraph):
        self.vector_store = vector_store
        self.agent_graph = agent_graph
    
    async def process_message(self, chat_id: str, message: str, db: Session) -> ChatResponse:
        """Process a chat message and return response"""
        try:
            # Check if chat session exists and is completed
            session = db.query(ChatSession).filter(ChatSession.chat_id == chat_id).first()
            if not session:
                return ChatResponse(
                    chat_id=chat_id,
                    response="Error: Chat session not found. Please process documentation first.",
                    sources=[]
                )
            
            if session.status != "completed":
                return ChatResponse(
                    chat_id=chat_id,
                    response="Error: Documentation is still being processed. Please wait.",
                    sources=[]
                )
            
            # Save user message to database
            user_message = ChatMessage(
                chat_id=chat_id,
                role="user",
                content=message
            )
            db.add(user_message)
            db.commit()
            
            # Get chat history for context
            chat_history = self._get_chat_history(chat_id, db)
            
            # Process with agent graph
            agent_response = await self.agent_graph.process_message(
                message=message,
                chat_id=chat_id,
                chat_history=chat_history
            )
            
            # Save assistant response to database
            assistant_message = ChatMessage(
                chat_id=chat_id,
                role="assistant",
                content=agent_response['response'],
                sources=agent_response.get('sources', [])
            )
            db.add(assistant_message)
            db.commit()
            
            return ChatResponse(
                chat_id=chat_id,
                response=agent_response['response'],
                sources=agent_response.get('sources', []),
                metadata=agent_response.get('metadata', {})
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return ChatResponse(
                chat_id=chat_id,
                response=f"Error processing your message: {str(e)}",
                sources=[]
            )
    
    def get_chat_history(self, chat_id: str, db: Session) -> ChatHistoryResponse:
        """Get chat history for a specific chat"""
        try:
            messages = self._get_chat_history(chat_id, db)
            
            # Format messages for response
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat(),
                    'sources': msg.sources or []
                })
            
            return ChatHistoryResponse(
                chat_id=chat_id,
                messages=formatted_messages
            )
            
        except Exception as e:
            logger.error(f"Error getting chat history: {str(e)}")
            return ChatHistoryResponse(
                chat_id=chat_id,
                messages=[]
            )
    
    def _get_chat_history(self, chat_id: str, db: Session) -> List[ChatMessage]:
        """Get chat history from database"""
        messages = db.query(ChatMessage).filter(
            ChatMessage.chat_id == chat_id
        ).order_by(ChatMessage.timestamp.asc()).all()
        
        return messages
    
    async def delete_chat(self, chat_id: str, db: Session) -> bool:
        """Delete a chat session and all associated data"""
        try:
            # Delete from database
            db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).delete()
            db.query(ChatSession).filter(ChatSession.chat_id == chat_id).delete()
            db.commit()
            
            # Delete from vector store
            await self.vector_store.delete_chat_data(chat_id)
            
            logger.info(f"Deleted chat session: {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting chat: {str(e)}")
            return False 