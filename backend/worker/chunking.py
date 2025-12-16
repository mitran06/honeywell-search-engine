"""
Advanced Chunking Module for Enterprise PDF Search

Implements 5 key improvements over simple word-based chunking:
1. Sentence-Aware Chunking - preserves semantic boundaries
2. Larger Chunk Size - optimized for MiniLM (256 token context)
3. Recursive/Hierarchical Chunking - paragraph → sentence → word fallback
4. Parent-Child Chunks - large context parents, small search children
5. Token-Based Sizing - accurate tokenizer instead of word count
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum

# Lazy-load tokenizer to avoid startup overhead
_tokenizer = None


def get_tokenizer():
    """Lazy-load the tokenizer for the embedding model."""
    global _tokenizer
    if _tokenizer is None:
        try:
            from transformers import AutoTokenizer
            _tokenizer = AutoTokenizer.from_pretrained(
                "sentence-transformers/all-MiniLM-L6-v2"
            )
        except Exception as e:
            logging.warning(f"Could not load tokenizer, falling back to word count: {e}")
            _tokenizer = "fallback"
    return _tokenizer


def token_count(text: str) -> int:
    """Get accurate token count using model tokenizer."""
    tokenizer = get_tokenizer()
    if tokenizer == "fallback":
        # Fallback: approximate 1 token ≈ 0.75 words
        return int(len(text.split()) / 0.75)
    return len(tokenizer.encode(text, add_special_tokens=False))


def word_count(text: str) -> int:
    """Simple word count."""
    return len(text.split())


# ------------------------------------------------------
# Configuration
# ------------------------------------------------------
class ChunkConfig:
    """Chunking configuration optimized for MiniLM-L6-v2."""
    
    # Parent chunks: large context for display and reranking
    PARENT_MAX_TOKENS = 500      # ~400 words
    PARENT_MIN_TOKENS = 100      # Don't create tiny parents
    
    # Child chunks: small for precise vector search
    CHILD_MAX_TOKENS = 200       # Within MiniLM's 256 token limit
    CHILD_MIN_TOKENS = 30        # Avoid too-small chunks
    
    # Overlap for continuity
    OVERLAP_SENTENCES = 1        # Sentence overlap between children
    
    # Sentence splitting patterns
    SENTENCE_PATTERN = re.compile(
        r'(?<=[.!?])\s+(?=[A-Z])|'  # Standard sentence end
        r'(?<=[.!?])\s*\n+|'        # Sentence + newline
        r'\n{2,}'                    # Paragraph breaks
    )
    
    # Paragraph splitting
    PARAGRAPH_PATTERN = re.compile(r'\n\s*\n+')


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""
    index: int
    text: str
    token_count: int
    char_count: int
    chunk_type: str  # "PARENT" or "CHILD"
    parent_index: Optional[int] = None  # For child chunks


# ------------------------------------------------------
# Sentence Splitting
# ------------------------------------------------------
def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences, preserving semantic boundaries."""
    # First normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    if not text:
        return []
    
    # Split on sentence boundaries
    sentences = ChunkConfig.SENTENCE_PATTERN.split(text)
    
    # Clean and filter
    result = []
    for sent in sentences:
        sent = sent.strip()
        if sent and len(sent) > 5:  # Skip tiny fragments
            result.append(sent)
    
    return result if result else [text]


def split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs."""
    paragraphs = ChunkConfig.PARAGRAPH_PATTERN.split(text)
    return [p.strip() for p in paragraphs if p.strip()]


# ------------------------------------------------------
# Recursive Chunking (Improvement #3)
# ------------------------------------------------------
def recursive_chunk(
    text: str, 
    max_tokens: int = ChunkConfig.PARENT_MAX_TOKENS
) -> List[str]:
    """
    Recursively chunk text by natural boundaries.
    
    Strategy:
    1. Try paragraphs first
    2. If paragraph too large, split by sentences
    3. If sentence too large, split by words (last resort)
    """
    if not text or not text.strip():
        return []
    
    # If text fits, return as-is
    if token_count(text) <= max_tokens:
        return [text.strip()] if text.strip() else []
    
    # Try splitting by paragraphs
    paragraphs = split_into_paragraphs(text)
    
    if len(paragraphs) > 1:
        # Recursively process each paragraph
        chunks = []
        for para in paragraphs:
            chunks.extend(recursive_chunk(para, max_tokens))
        return merge_small_chunks(chunks, ChunkConfig.PARENT_MIN_TOKENS)
    
    # Single paragraph too large: split by sentences
    sentences = split_into_sentences(text)
    
    if len(sentences) > 1:
        return sentence_chunk(sentences, max_tokens)
    
    # Single long sentence: hard split by tokens
    return hard_split(text, max_tokens)


def sentence_chunk(
    sentences: List[str], 
    max_tokens: int,
    overlap: int = ChunkConfig.OVERLAP_SENTENCES
) -> List[str]:
    """
    Chunk sentences into groups respecting token limits.
    Implements sentence-aware chunking (Improvement #1).
    """
    if not sentences:
        return []
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for sent in sentences:
        sent_tokens = token_count(sent)
        
        # If single sentence exceeds limit, hard split it
        if sent_tokens > max_tokens:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            chunks.extend(hard_split(sent, max_tokens))
            current_chunk = []
            current_tokens = 0
            continue
        
        # Check if adding this sentence exceeds limit
        if current_tokens + sent_tokens > max_tokens and current_chunk:
            chunks.append(" ".join(current_chunk))
            # Keep overlap sentences for context continuity
            if overlap > 0 and len(current_chunk) >= overlap:
                current_chunk = current_chunk[-overlap:]
                current_tokens = sum(token_count(s) for s in current_chunk)
            else:
                current_chunk = []
                current_tokens = 0
        
        current_chunk.append(sent)
        current_tokens += sent_tokens
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks


def hard_split(text: str, max_tokens: int) -> List[str]:
    """Last resort: split by word count when sentences are too long."""
    words = text.split()
    if not words:
        return []
    
    # Approximate words per chunk (tokens ≈ words * 1.3)
    words_per_chunk = int(max_tokens * 0.75)
    
    chunks = []
    for i in range(0, len(words), words_per_chunk):
        chunk = " ".join(words[i:i + words_per_chunk])
        if chunk:
            chunks.append(chunk)
    
    return chunks


def merge_small_chunks(chunks: List[str], min_tokens: int) -> List[str]:
    """Merge chunks that are too small."""
    if not chunks:
        return []
    
    result = []
    current = chunks[0]
    
    for chunk in chunks[1:]:
        if token_count(current) < min_tokens:
            current = current + " " + chunk
        else:
            result.append(current)
            current = chunk
    
    if current:
        result.append(current)
    
    return result


# ------------------------------------------------------
# Parent-Child Chunking (Improvement #4)
# ------------------------------------------------------
def create_parent_child_chunks(
    text: str,
    page_num: int
) -> Tuple[List[Chunk], List[Chunk]]:
    """
    Create hierarchical parent-child chunks.
    
    - Parents: Large context chunks (500 tokens) for reranking and display
    - Children: Small precise chunks (200 tokens) for vector search
    
    Returns: (parent_chunks, child_chunks)
    """
    if not text or not text.strip():
        return [], []
    
    # Step 1: Create parent chunks using recursive chunking
    parent_texts = recursive_chunk(text, ChunkConfig.PARENT_MAX_TOKENS)
    parent_texts = merge_small_chunks(parent_texts, ChunkConfig.PARENT_MIN_TOKENS)
    
    parents = []
    children = []
    
    for parent_idx, parent_text in enumerate(parent_texts):
        parent_tokens = token_count(parent_text)
        
        parent = Chunk(
            index=parent_idx,
            text=parent_text,
            token_count=parent_tokens,
            char_count=len(parent_text),
            chunk_type="PARENT",
            parent_index=None
        )
        parents.append(parent)
        
        # Step 2: Create child chunks from each parent
        if parent_tokens <= ChunkConfig.CHILD_MAX_TOKENS:
            # Parent is small enough to be its own child
            child = Chunk(
                index=0,
                text=parent_text,
                token_count=parent_tokens,
                char_count=len(parent_text),
                chunk_type="CHILD",
                parent_index=parent_idx
            )
            children.append(child)
        else:
            # Split parent into smaller children
            child_sentences = split_into_sentences(parent_text)
            child_texts = sentence_chunk(
                child_sentences, 
                ChunkConfig.CHILD_MAX_TOKENS,
                overlap=ChunkConfig.OVERLAP_SENTENCES
            )
            
            for child_idx, child_text in enumerate(child_texts):
                child = Chunk(
                    index=child_idx,
                    text=child_text,
                    token_count=token_count(child_text),
                    char_count=len(child_text),
                    chunk_type="CHILD",
                    parent_index=parent_idx
                )
                children.append(child)
    
    return parents, children


# ------------------------------------------------------
# Main Entry Point
# ------------------------------------------------------
def chunk_document_page(
    page_text: str,
    page_num: int
) -> Tuple[List[Chunk], List[Chunk]]:
    """
    Process a single page of text and return parent + child chunks.
    
    This is the main entry point for the chunking pipeline.
    
    Args:
        page_text: Raw text from PDF page
        page_num: 1-indexed page number
        
    Returns:
        Tuple of (parent_chunks, child_chunks)
    """
    return create_parent_child_chunks(page_text, page_num)


# ------------------------------------------------------
# Legacy Compatibility
# ------------------------------------------------------
def chunk_text_legacy(
    text: str, 
    max_tokens: int = 250, 
    overlap_ratio: float = 0.15
) -> List[Tuple[int, str]]:
    """
    Legacy-compatible chunking function.
    
    Improved from original:
    - max_tokens: 120 → 250 (better for MiniLM)
    - overlap_ratio: 0.2 → 0.15 (less redundancy with larger chunks)
    - Uses sentence-aware splitting
    """
    sentences = split_into_sentences(text)
    chunks = sentence_chunk(sentences, max_tokens, overlap=1)
    
    return [(i, chunk) for i, chunk in enumerate(chunks)]


# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chunking")
