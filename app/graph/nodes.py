from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from app.services.vector_store import VectorStore
from app.config import settings
import re
import logging

logger = logging.getLogger(__name__)


class GraphNodes:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=0.1,
            api_key=settings.openai_api_key
        )
    
    async def input_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Input node - receives user message"""
        return {
            **state,
            "user_message": state.get("message", ""),
            "current_step": "input_received"
        }
    
    async def intent_analysis_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user intent"""
        user_message = state.get("user_message", "")
        chat_history = state.get("chat_history", [])
        
        # Create context from chat history
        context = ""
        if chat_history:
            recent_messages = chat_history[-3:]  # Last 3 messages for context
            context = "\n".join([f"{msg.role}: {msg.content}" for msg in recent_messages])
        
        # Analyze intent using LLM
        intent_prompt = f"""
        Analyze the user's intent based on their message and conversation context.
        
        Conversation Context:
        {context}
        
        User Message: {user_message}
        
        Classify the intent into one of these categories:
        1. GENERAL_QUESTION - General questions about the documentation
        2. CODE_QUESTION - Questions about specific code or implementation
        3. FOLLOW_UP - Follow-up questions that reference previous conversation
        4. CLARIFICATION_NEEDED - Unclear or ambiguous questions
        
        Respond with only the category name.
        """
        
        try:
            intent_response = await self.llm.ainvoke(intent_prompt)
            intent = intent_response.content.strip().upper()
            
            # Validate intent
            valid_intents = ["GENERAL_QUESTION", "CODE_QUESTION", "FOLLOW_UP", "CLARIFICATION_NEEDED"]
            if intent not in valid_intents:
                intent = "GENERAL_QUESTION"  # Default fallback
            
            return {
                **state,
                "intent": intent,
                "current_step": "intent_analyzed"
            }
            
        except Exception as e:
            logger.error(f"Error in intent analysis: {str(e)}")
            return {
                **state,
                "intent": "GENERAL_QUESTION",
                "current_step": "intent_analyzed"
            }
    
    async def conditional_router(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Route to appropriate node based on intent"""
        intent = state.get("intent", "GENERAL_QUESTION")
        
        routing_map = {
            "GENERAL_QUESTION": "rag_node",
            "CODE_QUESTION": "code_analysis_node",
            "FOLLOW_UP": "rag_node",
            "CLARIFICATION_NEEDED": "clarification_node"
        }
        
        next_node = routing_map.get(intent, "rag_node")
        
        return {
            **state,
            "next_node": next_node,
            "current_step": "routed"
        }
    
    async def rag_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieval Augmented Generation node"""
        user_message = state.get("user_message", "")
        chat_id = state.get("chat_id", "")
        chat_history = state.get("chat_history", [])
        
        try:
            # Search for relevant chunks
            relevant_chunks = await self.vector_store.search(user_message, chat_id, top_k=5)
            
            if not relevant_chunks:
                return {
                    **state,
                    "retrieved_chunks": [],
                    "current_step": "rag_completed",
                    "response": "I couldn't find relevant information in the documentation to answer your question. Could you please rephrase or ask about a different topic?"
                }
            
            # Create context from retrieved chunks
            context = "\n\n".join([chunk['content'] for chunk in relevant_chunks])
            
            # Create conversation history for context
            conversation_context = ""
            if chat_history:
                recent_messages = chat_history[-5:]  # Last 5 messages
                conversation_context = "\n".join([f"{msg.role}: {msg.content}" for msg in recent_messages])
            
            # Generate response using LLM
            response_prompt = f"""
            You are a helpful assistant that answers questions about technical documentation.
            
            Conversation History:
            {conversation_context}
            
            Relevant Documentation Context:
            {context}
            
            User Question: {user_message}
            
            Please provide a comprehensive and accurate answer based on the documentation context.
            If the answer includes code, format it properly with markdown.
            If you're not sure about something, say so clearly.
            
            Answer:
            """
            
            response = await self.llm.ainvoke(response_prompt)
            
            # Extract sources from chunks
            sources = list(set([chunk['metadata'].get('url', '') for chunk in relevant_chunks if chunk['metadata'].get('url')]))
            
            return {
                **state,
                "retrieved_chunks": relevant_chunks,
                "response": response.content,
                "sources": sources,
                "current_step": "rag_completed"
            }
            
        except Exception as e:
            logger.error(f"Error in RAG node: {str(e)}")
            return {
                **state,
                "response": f"Error retrieving information: {str(e)}",
                "sources": [],
                "current_step": "rag_completed"
            }
    
    async def code_analysis_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Specialized node for code-related questions"""
        user_message = state.get("user_message", "")
        chat_id = state.get("chat_id", "")
        
        try:
            # Search specifically for code chunks
            code_chunks = await self.vector_store.search(user_message, chat_id, top_k=10)
            
            # Filter for code-related chunks
            code_relevant_chunks = [
                chunk for chunk in code_chunks 
                if chunk['metadata'].get('chunk_type') == 'code' or 
                   'code' in chunk['content'].lower() or
                   '```' in chunk['content']
            ]
            
            if not code_relevant_chunks:
                # Fallback to general RAG
                return await self.rag_node(state)
            
            # Create context from code chunks
            code_context = "\n\n".join([chunk['content'] for chunk in code_relevant_chunks])
            
            # Generate code-specific response
            code_prompt = f"""
            You are a technical assistant specializing in code analysis and explanation.
            
            Code Context:
            {code_context}
            
            User Question: {user_message}
            
            Please provide a detailed explanation of the code, including:
            1. What the code does
            2. How it works
            3. Any important patterns or concepts
            4. Examples if relevant
            
            Format code blocks properly with markdown syntax highlighting.
            """
            
            response = await self.llm.ainvoke(code_prompt)
            
            # Extract sources
            sources = list(set([chunk['metadata'].get('url', '') for chunk in code_relevant_chunks if chunk['metadata'].get('url')]))
            
            return {
                **state,
                "retrieved_chunks": code_relevant_chunks,
                "response": response.content,
                "sources": sources,
                "current_step": "code_analysis_completed"
            }
            
        except Exception as e:
            logger.error(f"Error in code analysis node: {str(e)}")
            return await self.rag_node(state)  # Fallback to general RAG
    
    async def clarification_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Node for handling unclear questions"""
        user_message = state.get("user_message", "")
        
        clarification_prompt = f"""
        The user's question seems unclear or ambiguous:
        
        User Question: {user_message}
        
        Please ask for clarification to better understand what they're looking for.
        Be specific about what additional information would help you provide a better answer.
        """
        
        try:
            response = await self.llm.ainvoke(clarification_prompt)
            
            return {
                **state,
                "response": response.content,
                "sources": [],
                "current_step": "clarification_requested"
            }
            
        except Exception as e:
            logger.error(f"Error in clarification node: {str(e)}")
            return {
                **state,
                "response": "I'm not sure I understand your question. Could you please rephrase it or provide more details?",
                "sources": [],
                "current_step": "clarification_requested"
            }
    
    async def code_formatting_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Format code in response"""
        response = state.get("response", "")
        
        # Check if response contains code blocks
        if "```" in response:
            # Code is already formatted, just ensure proper formatting
            formatted_response = response
            
            # Ensure code blocks have language specification
            formatted_response = re.sub(
                r'```(\w+)?\n',
                lambda m: f'```{m.group(1) or "text"}\n',
                formatted_response
            )
        else:
            formatted_response = response
        
        return {
            **state,
            "response": formatted_response,
            "current_step": "code_formatted"
        }
    
    async def memory_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Memory node - update conversation state"""
        chat_history = state.get("chat_history", [])
        user_message = state.get("user_message", "")
        response = state.get("response", "")
        
        # Update memory with current exchange
        updated_memory = {
            "last_user_message": user_message,
            "last_assistant_response": response,
            "conversation_length": len(chat_history) + 2,  # +2 for current exchange
            "current_step": "memory_updated"
        }
        
        return {
            **state,
            "memory": updated_memory
        } 