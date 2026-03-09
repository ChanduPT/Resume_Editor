"""
RAG (Retrieval Augmented Generation) Engine for Help Mode
Loads knowledge base documents, chunks them, generates embeddings,
and performs semantic search to retrieve relevant context.
"""

import os
import re
import logging
from typing import List, Dict, Tuple
from pathlib import Path
import google.generativeai as genai
import numpy as np
from functools import lru_cache

from .config import (
    RAG_CHUNK_SIZE,
    RAG_CHUNK_OVERLAP,
    RAG_TOP_K_RESULTS,
    RAG_SIMILARITY_THRESHOLD
)

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a chunk of text from a document"""
    def __init__(self, text: str, source: str, chunk_id: int):
        self.text = text
        self.source = source  # filename
        self.chunk_id = chunk_id
        self.embedding: np.ndarray = None
    
    def __repr__(self):
        return f"DocumentChunk(source={self.source}, chunk_id={self.chunk_id}, text_len={len(self.text)})"


class RAGEngine:
    """
    RAG Engine for retrieving relevant documentation
    Uses Gemini Embedding API for semantic search
    """
    
    def __init__(self, knowledge_base_dir: str):
        self.knowledge_base_dir = Path(knowledge_base_dir)
        self.chunks: List[DocumentChunk] = []
        self.initialized = False
        
        # Initialize Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")
        genai.configure(api_key=api_key)
        
        logger.info(f"RAG Engine initialized with knowledge base: {knowledge_base_dir}")
    
    def load_knowledge_base(self):
        """
        Load all markdown files from knowledge base directory,
        chunk them, and generate embeddings
        """
        if self.initialized:
            logger.info("Knowledge base already loaded")
            return
        
        logger.info("Loading knowledge base documents...")
        
        # Find all markdown files
        md_files = list(self.knowledge_base_dir.glob("*.md"))
        if not md_files:
            raise ValueError(f"No markdown files found in {self.knowledge_base_dir}")
        
        logger.info(f"Found {len(md_files)} markdown files")
        
        # Process each file
        for md_file in md_files:
            self._process_document(md_file)
        
        # Generate embeddings for all chunks
        logger.info(f"Generating embeddings for {len(self.chunks)} chunks...")
        self._generate_embeddings()
        
        self.initialized = True
        logger.info(f"Knowledge base loaded successfully: {len(self.chunks)} chunks indexed")
    
    def _process_document(self, filepath: Path):
        """
        Load a markdown file and split into chunks
        """
        logger.info(f"Processing document: {filepath.name}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by headers first to maintain context
        sections = self._split_by_headers(content)
        
        # Further chunk large sections
        chunk_id = 0
        for section_title, section_text in sections:
            text_chunks = self._chunk_text(section_text, section_title)
            
            for text in text_chunks:
                chunk = DocumentChunk(
                    text=text,
                    source=filepath.name,
                    chunk_id=chunk_id
                )
                self.chunks.append(chunk)
                chunk_id += 1
        
        logger.info(f"Created {chunk_id} chunks from {filepath.name}")
    
    def _split_by_headers(self, content: str) -> List[Tuple[str, str]]:
        """
        Split markdown content by headers (##) to maintain semantic sections
        Returns list of (title, content) tuples
        """
        sections = []
        current_title = "Introduction"
        current_content = []
        
        for line in content.split('\n'):
            # Check if line is a header
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                # Save previous section
                if current_content:
                    sections.append((current_title, '\n'.join(current_content)))
                
                # Start new section
                current_title = header_match.group(2).strip()
                current_content = []
            else:
                current_content.append(line)
        
        # Save last section
        if current_content:
            sections.append((current_title, '\n'.join(current_content)))
        
        return sections
    
    def _chunk_text(self, text: str, title: str = "") -> List[str]:
        """
        Split text into overlapping chunks
        Each chunk includes the section title for context
        """
        # Clean text
        text = text.strip()
        if not text:
            return []
        
        # Prepend title for context
        if title:
            text = f"## {title}\n\n{text}"
        
        # If text is small enough, return as single chunk
        if len(text) <= RAG_CHUNK_SIZE:
            return [text]
        
        # Split into sentences (simple approach)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # If adding this sentence exceeds chunk size, save current chunk
            if current_length + sentence_length > RAG_CHUNK_SIZE and current_chunk:
                chunks.append(' '.join(current_chunk))
                
                # Start new chunk with overlap
                overlap_text = ' '.join(current_chunk[-2:])  # Last 2 sentences as overlap
                current_chunk = [overlap_text, sentence] if len(overlap_text) < RAG_CHUNK_OVERLAP else [sentence]
                current_length = len(' '.join(current_chunk))
            else:
                current_chunk.append(sentence)
                current_length += sentence_length
        
        # Add last chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _generate_embeddings(self):
        """
        Generate embeddings for all chunks using Gemini Embedding API
        """
        # Batch process for efficiency
        batch_size = 100
        texts = [chunk.text for chunk in self.chunks]
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            try:
                # Generate embeddings using Gemini
                result = genai.embed_content(
                    model="models/embedding-001",
                    content=batch
                )
                
                # Store embeddings
                embeddings = result['embedding'] if isinstance(result['embedding'][0], list) else [result['embedding']]
                for j, embedding in enumerate(embeddings):
                    chunk_idx = i + j
                    if chunk_idx < len(self.chunks):
                        self.chunks[chunk_idx].embedding = np.array(embedding)
                
                logger.info(f"Generated embeddings for batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
                
            except Exception as e:
                logger.error(f"Error generating embeddings for batch {i//batch_size + 1}: {e}")
                raise
    
    @lru_cache(maxsize=100)
    def search(self, query: str, top_k: int = RAG_TOP_K_RESULTS) -> List[Dict]:
        """
        Perform semantic search to find most relevant document chunks
        
        Args:
            query: User's question
            top_k: Number of results to return
        
        Returns:
            List of dictionaries with 'text', 'source', 'score'
        """
        if not self.initialized:
            self.load_knowledge_base()
        
        logger.info(f"Searching for: {query[:100]}...")
        
        try:
            # Generate embedding for query
            result = genai.embed_content(
                model="models/embedding-001",
                content=query
            )
            query_embedding = np.array(result['embedding'])
            
            # Calculate cosine similarity with all chunks
            similarities = []
            for chunk in self.chunks:
                similarity = self._cosine_similarity(query_embedding, chunk.embedding)
                similarities.append((chunk, similarity))
            
            # Sort by similarity (highest first)
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Filter by threshold and take top_k
            results = []
            for chunk, score in similarities[:top_k]:
                if score >= RAG_SIMILARITY_THRESHOLD:
                    results.append({
                        'text': chunk.text,
                        'source': chunk.source,
                        'score': float(score),
                        'chunk_id': chunk.chunk_id
                    })
            
            logger.info(f"Found {len(results)} relevant chunks (threshold: {RAG_SIMILARITY_THRESHOLD})")
            
            return results
            
        except Exception as e:
            logger.error(f"Error during search: {e}")
            raise
    
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def get_context_for_query(self, query: str) -> str:
        """
        Get formatted context string for LLM from search results
        
        Args:
            query: User's question
        
        Returns:
            Formatted string with relevant documentation
        """
        results = self.search(query)
        
        if not results:
            return "No relevant documentation found."
        
        # Format context
        context_parts = ["Here is relevant documentation:\n"]
        
        for i, result in enumerate(results, 1):
            context_parts.append(f"\n--- Source: {result['source']} (relevance: {result['score']:.2f}) ---")
            context_parts.append(result['text'])
        
        return '\n'.join(context_parts)


# Global singleton instance
_rag_engine: RAGEngine = None


def get_rag_engine() -> RAGEngine:
    """
    Get or create RAG engine singleton
    """
    global _rag_engine
    if _rag_engine is None:
        knowledge_base_dir = os.path.join(
            os.path.dirname(__file__),
            'knowledge_base'
        )
        _rag_engine = RAGEngine(knowledge_base_dir)
        _rag_engine.load_knowledge_base()
    return _rag_engine


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test loading
    engine = get_rag_engine()
    
    # Test search
    test_queries = [
        "How do I upload a resume?",
        "What formats are supported?",
        "How does AI tailoring work?",
        "Can I edit the generated resume?",
    ]
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"{'='*80}")
        
        results = engine.search(query, top_k=2)
        for i, result in enumerate(results, 1):
            print(f"\n[Result {i}] Score: {result['score']:.3f} | Source: {result['source']}")
            print(f"{result['text'][:200]}...")
