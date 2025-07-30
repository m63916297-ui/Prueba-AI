import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.embedding_model = SentenceTransformer(settings.embedding_model)
        self.collections = {}
    
    async def add_chunks(self, chunks: List[Dict[str, Any]], chat_id: str):
        """Add chunks to vector store"""
        try:
            # Get or create collection for this chat
            collection_name = f"chat_{chat_id}"
            if collection_name not in self.collections:
                self.collections[collection_name] = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"chat_id": chat_id}
                )
            
            collection = self.collections[collection_name]
            
            # Prepare data for ChromaDB
            documents = []
            metadatas = []
            ids = []
            
            for chunk in chunks:
                documents.append(chunk['content'])
                metadatas.append(chunk['metadata'])
                ids.append(chunk['id'])
            
            # Add to collection
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info(f"Added {len(chunks)} chunks to vector store for chat_id: {chat_id}")
            
        except Exception as e:
            logger.error(f"Error adding chunks to vector store: {str(e)}")
            raise
    
    async def search(self, query: str, chat_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant chunks"""
        try:
            collection_name = f"chat_{chat_id}"
            if collection_name not in self.collections:
                self.collections[collection_name] = self.client.get_collection(
                    name=collection_name
                )
            
            collection = self.collections[collection_name]
            
            # Search in collection
            results = collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    formatted_results.append({
                        'content': doc,
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if results['distances'] else None
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching vector store: {str(e)}")
            return []
    
    async def delete_chat_data(self, chat_id: str):
        """Delete all data for a specific chat"""
        try:
            collection_name = f"chat_{chat_id}"
            if collection_name in self.collections:
                del self.collections[collection_name]
            
            # Delete collection from ChromaDB
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted vector store data for chat_id: {chat_id}")
            
        except Exception as e:
            logger.error(f"Error deleting chat data: {str(e)}")
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a text"""
        return self.embedding_model.encode(text).tolist()
    
    async def similarity_search(self, query: str, chat_id: str, top_k: int = 5, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Search with similarity threshold"""
        results = await self.search(query, chat_id, top_k)
        
        # Filter by similarity threshold
        filtered_results = []
        for result in results:
            if result['distance'] is None or result['distance'] <= threshold:
                filtered_results.append(result)
        
        return filtered_results 