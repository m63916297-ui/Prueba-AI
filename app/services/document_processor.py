import asyncio
import uuid
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
import re
from sqlalchemy.orm import Session
from app.database.models import ChatSession, DocumentChunk
from app.services.vector_store import VectorStore
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
    
    async def process_documentation(self, url: str, chat_id: str, db: Session) -> bool:
        """Process documentation from URL and store in vector database"""
        try:
            # Update status to processing
            self._update_session_status(db, chat_id, "processing", 10)
            
            # Fetch and parse HTML
            html_content = await self._fetch_url(url)
            if not html_content:
                self._update_session_status(db, chat_id, "failed", 0, "Failed to fetch URL")
                return False
            
            self._update_session_status(db, chat_id, "processing", 30)
            
            # Extract and clean content
            content = self._extract_content(html_content)
            if not content:
                self._update_session_status(db, chat_id, "failed", 0, "No content extracted")
                return False
            
            self._update_session_status(db, chat_id, "processing", 50)
            
            # Create intelligent chunks
            chunks = self._create_intelligent_chunks(content, url)
            if not chunks:
                self._update_session_status(db, chat_id, "failed", 0, "No chunks created")
                return False
            
            self._update_session_status(db, chat_id, "processing", 70)
            
            # Store chunks in database and vector store
            await self._store_chunks(chunks, chat_id, db)
            
            self._update_session_status(db, chat_id, "completed", 100)
            logger.info(f"Successfully processed documentation for chat_id: {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing documentation: {str(e)}")
            self._update_session_status(db, chat_id, "failed", 0, str(e))
            return False
    
    async def _fetch_url(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {str(e)}")
            return None
    
    def _extract_content(self, html_content: str) -> Dict[str, Any]:
        """Extract and clean content from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        content = {
            'title': self._extract_title(soup),
            'sections': self._extract_sections(soup),
            'code_blocks': self._extract_code_blocks(soup)
        }
        
        return content
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title"""
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text().strip()
        return "Untitled"
    
    def _extract_sections(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract content sections"""
        sections = []
        
        # Find main content area
        main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'content|main|article'))
        if not main_content:
            main_content = soup.find('body')
        
        if main_content:
            # Extract headings and their content
            headings = main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            
            for i, heading in enumerate(headings):
                section = {
                    'title': heading.get_text().strip(),
                    'level': int(heading.name[1]),
                    'content': '',
                    'id': heading.get('id', f'section_{i}')
                }
                
                # Get content until next heading
                content_parts = []
                current = heading.next_sibling
                while current and not (hasattr(current, 'name') and current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    if hasattr(current, 'get_text'):
                        text = current.get_text().strip()
                        if text:
                            content_parts.append(text)
                    current = current.next_sibling
                
                section['content'] = ' '.join(content_parts)
                if section['content']:
                    sections.append(section)
        
        return sections
    
    def _extract_code_blocks(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract code blocks"""
        code_blocks = []
        
        for code_tag in soup.find_all(['pre', 'code']):
            if code_tag.name == 'pre':
                code_content = code_tag.get_text().strip()
                language = code_tag.find('code', class_=re.compile(r'language-'))
                if language:
                    lang = language.get('class')[0].replace('language-', '')
                else:
                    lang = 'text'
            else:
                code_content = code_tag.get_text().strip()
                lang = 'text'
            
            if code_content:
                code_blocks.append({
                    'content': code_content,
                    'language': lang,
                    'id': f'code_{len(code_blocks)}'
                })
        
        return code_blocks
    
    def _create_intelligent_chunks(self, content: Dict[str, Any], url: str) -> List[Dict[str, Any]]:
        """Create intelligent chunks preserving semantic coherence"""
        chunks = []
        
        # Add title as a chunk
        if content['title']:
            chunks.append({
                'id': str(uuid.uuid4()),
                'content': f"Title: {content['title']}",
                'type': 'title',
                'metadata': {
                    'url': url,
                    'section': 'title',
                    'chunk_type': 'title'
                }
            })
        
        # Process sections
        for section in content['sections']:
            if len(section['content']) <= settings.max_chunk_size:
                # Section fits in one chunk
                chunks.append({
                    'id': str(uuid.uuid4()),
                    'content': f"{section['title']}\n\n{section['content']}",
                    'type': 'section',
                    'metadata': {
                        'url': url,
                        'section': section['title'],
                        'section_id': section['id'],
                        'level': section['level'],
                        'chunk_type': 'section'
                    }
                })
            else:
                # Split section into multiple chunks
                section_chunks = self._split_text_intelligently(
                    section['content'], 
                    section['title'],
                    url,
                    section['id'],
                    section['level']
                )
                chunks.extend(section_chunks)
        
        # Process code blocks
        for code_block in content['code_blocks']:
            chunks.append({
                'id': str(uuid.uuid4()),
                'content': f"Code Block ({code_block['language']}):\n```{code_block['language']}\n{code_block['content']}\n```",
                'type': 'code',
                'metadata': {
                    'url': url,
                    'language': code_block['language'],
                    'code_id': code_block['id'],
                    'chunk_type': 'code'
                }
            })
        
        return chunks
    
    def _split_text_intelligently(self, text: str, title: str, url: str, section_id: str, level: int) -> List[Dict[str, Any]]:
        """Split text intelligently preserving semantic coherence"""
        chunks = []
        
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        current_chunk = f"{title}\n\n"
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # If adding this paragraph would exceed chunk size, save current chunk and start new one
            if len(current_chunk) + len(paragraph) > settings.max_chunk_size and current_chunk.strip():
                chunks.append({
                    'id': str(uuid.uuid4()),
                    'content': current_chunk.strip(),
                    'type': 'section',
                    'metadata': {
                        'url': url,
                        'section': title,
                        'section_id': section_id,
                        'level': level,
                        'chunk_type': 'section_part'
                    }
                })
                current_chunk = f"{title} (continued)\n\n"
            
            current_chunk += paragraph + "\n\n"
        
        # Add remaining content
        if current_chunk.strip():
            chunks.append({
                'id': str(uuid.uuid4()),
                'content': current_chunk.strip(),
                'type': 'section',
                'metadata': {
                    'url': url,
                    'section': title,
                    'section_id': section_id,
                    'level': level,
                    'chunk_type': 'section_part'
                }
            })
        
        return chunks
    
    async def _store_chunks(self, chunks: List[Dict[str, Any]], chat_id: str, db: Session):
        """Store chunks in database and vector store"""
        # Store in database
        for chunk in chunks:
            db_chunk = DocumentChunk(
                chat_id=chat_id,
                chunk_id=chunk['id'],
                content=chunk['content'],
                metadata=chunk['metadata']
            )
            db.add(db_chunk)
        
        db.commit()
        
        # Store in vector store
        await self.vector_store.add_chunks(chunks, chat_id)
    
    def _update_session_status(self, db: Session, chat_id: str, status: str, progress: int, error_message: str = None):
        """Update chat session status"""
        session = db.query(ChatSession).filter(ChatSession.chat_id == chat_id).first()
        if session:
            session.status = status
            session.progress = progress
            if error_message:
                session.error_message = error_message
            db.commit() 