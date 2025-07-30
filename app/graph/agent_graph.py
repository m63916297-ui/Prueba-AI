from typing import Dict, Any, List, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.graph.nodes import GraphNodes
from app.services.vector_store import VectorStore
import logging

logger = logging.getLogger(__name__)


class AgentGraph:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.nodes = GraphNodes(vector_store)
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        # Create state graph
        workflow = StateGraph(Annotated[Dict[str, Any], "state"])
        
        # Add nodes
        workflow.add_node("input_node", self.nodes.input_node)
        workflow.add_node("intent_analysis_node", self.nodes.intent_analysis_node)
        workflow.add_node("conditional_router", self.nodes.conditional_router)
        workflow.add_node("rag_node", self.nodes.rag_node)
        workflow.add_node("code_analysis_node", self.nodes.code_analysis_node)
        workflow.add_node("clarification_node", self.nodes.clarification_node)
        workflow.add_node("code_formatting_node", self.nodes.code_formatting_node)
        workflow.add_node("memory_node", self.nodes.memory_node)
        
        # Define edges
        workflow.set_entry_point("input_node")
        
        # Linear flow from input to intent analysis
        workflow.add_edge("input_node", "intent_analysis_node")
        workflow.add_edge("intent_analysis_node", "conditional_router")
        
        # Conditional routing based on intent
        workflow.add_conditional_edges(
            "conditional_router",
            self._route_based_on_intent,
            {
                "rag_node": "rag_node",
                "code_analysis_node": "code_analysis_node",
                "clarification_node": "clarification_node"
            }
        )
        
        # All processing nodes go to code formatting
        workflow.add_edge("rag_node", "code_formatting_node")
        workflow.add_edge("code_analysis_node", "code_formatting_node")
        workflow.add_edge("clarification_node", "code_formatting_node")
        
        # Code formatting goes to memory
        workflow.add_edge("code_formatting_node", "memory_node")
        
        # Memory is the end
        workflow.add_edge("memory_node", END)
        
        return workflow.compile(checkpointer=MemorySaver())
    
    def _route_based_on_intent(self, state: Dict[str, Any]) -> str:
        """Route to appropriate node based on intent"""
        next_node = state.get("next_node", "rag_node")
        return next_node
    
    async def process_message(self, message: str, chat_id: str, chat_history: List) -> Dict[str, Any]:
        """Process a message through the graph"""
        try:
            # Prepare initial state
            initial_state = {
                "message": message,
                "chat_id": chat_id,
                "chat_history": chat_history,
                "current_step": "started"
            }
            
            # Run the graph
            config = {"configurable": {"thread_id": chat_id}}
            result = await self.graph.ainvoke(initial_state, config)
            
            # Extract final response
            final_state = result.get("memory", {})
            
            return {
                "response": final_state.get("response", "No response generated"),
                "sources": final_state.get("sources", []),
                "metadata": {
                    "intent": final_state.get("intent", "unknown"),
                    "current_step": final_state.get("current_step", "unknown"),
                    "retrieved_chunks_count": len(final_state.get("retrieved_chunks", []))
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing message through graph: {str(e)}")
            return {
                "response": f"Error processing your message: {str(e)}",
                "sources": [],
                "metadata": {"error": str(e)}
            }
    
    def get_graph_info(self) -> Dict[str, Any]:
        """Get information about the graph structure"""
        return {
            "nodes": [
                "input_node",
                "intent_analysis_node", 
                "conditional_router",
                "rag_node",
                "code_analysis_node",
                "clarification_node",
                "code_formatting_node",
                "memory_node"
            ],
            "edges": [
                "input_node → intent_analysis_node",
                "intent_analysis_node → conditional_router",
                "conditional_router → rag_node (GENERAL_QUESTION/FOLLOW_UP)",
                "conditional_router → code_analysis_node (CODE_QUESTION)",
                "conditional_router → clarification_node (CLARIFICATION_NEEDED)",
                "rag_node → code_formatting_node",
                "code_analysis_node → code_formatting_node", 
                "clarification_node → code_formatting_node",
                "code_formatting_node → memory_node",
                "memory_node → END"
            ]
        } 