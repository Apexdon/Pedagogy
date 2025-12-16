"""
Text Chunking Module

Splits documents into semantic chunks for embedding.
Uses sentence-aware chunking with configurable overlap.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""

    content: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Calculate additional metadata after initialization."""
        if 'char_count' not in self.metadata:
            self.metadata['char_count'] = len(self.content)
        if 'word_count' not in self.metadata:
            self.metadata['word_count'] = len(self.content.split())


class TextChunker:
    """
    Chunks text into overlapping segments for embedding.

    Uses sentence boundaries when possible to avoid cutting mid-sentence.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 50
    ):
        """
        Initialize the text chunker.

        Args:
            chunk_size: Target size for each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum chunk size (smaller chunks are discarded)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Split text into overlapping chunks.

        Args:
            text: The text to chunk
            metadata: Optional metadata to include with each chunk

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        # Normalize whitespace but preserve paragraph breaks
        text = re.sub(r'[ \t]+', ' ', text)  # Collapse horizontal whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 newlines
        text = text.strip()

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            # Calculate end position
            end = min(start + self.chunk_size, len(text))

            # If not at the end, try to find a good break point
            if end < len(text):
                end = self._find_break_point(text, start, end)

            chunk_content = text[start:end].strip()

            # Only create chunk if it meets minimum size
            if len(chunk_content) >= self.min_chunk_size:
                chunk_metadata = metadata.copy() if metadata else {}

                chunks.append(Chunk(
                    content=chunk_content,
                    chunk_index=chunk_index,
                    start_char=start,
                    end_char=end,
                    metadata=chunk_metadata
                ))
                chunk_index += 1

            # Move start position, accounting for overlap
            start = max(start + 1, end - self.chunk_overlap)

        logger.debug(f"Created {len(chunks)} chunks from {len(text)} characters")
        return chunks

    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """
        Find a natural break point (sentence end) near the end position.

        Looks for sentence-ending punctuation followed by space.
        Falls back to paragraph break, then word boundary if no sentence end found.
        """
        search_text = text[start:end]

        # Priority 1: Paragraph break (double newline)
        para_break = search_text.rfind('\n\n')
        if para_break > len(search_text) * 0.5:  # Only if in latter half
            return start + para_break + 2

        # Priority 2: Sentence endings (., !, ?) followed by space or newline
        sentence_endings = []
        for m in re.finditer(r'[.!?][\s\n]', search_text):
            sentence_endings.append(m.end() + start)

        if sentence_endings:
            # Return the last sentence ending before our target
            return sentence_endings[-1]

        # Priority 3: Single newline
        newline = search_text.rfind('\n')
        if newline > len(search_text) * 0.3:  # Only if reasonably far in
            return start + newline + 1

        # Priority 4: Word boundary (space)
        last_space = search_text.rfind(' ')
        if last_space > 0:
            return start + last_space

        # Fallback: just use the end position
        return end


class InstructionAwareChunker(TextChunker):
    """
    Extended chunker that preserves instruction step boundaries.

    Useful for SOPs and walkthroughs where steps should not be split.
    Falls back to regular chunking if no instruction patterns are detected.
    """

    # Patterns that indicate instruction steps
    STEP_PATTERNS = [
        r'^\s*\d+[.)]\s',           # 1. or 1)
        r'^\s*Step\s+\d+',          # Step 1
        r'^\s*[-*]\s',              # Bullet points
        r'^\s*[a-zA-Z][.)]\s',      # a. or a)
        r'^\s*\[\s*\d+\s*\]',       # [1]
    ]

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 50,
        combine_short_steps: bool = True
    ):
        """
        Initialize the instruction-aware chunker.

        Args:
            chunk_size: Target size for each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum chunk size
            combine_short_steps: Whether to combine short steps into larger chunks
        """
        super().__init__(chunk_size, chunk_overlap, min_chunk_size)
        self.combine_short_steps = combine_short_steps

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk text while trying to keep instruction steps together.

        If no instruction patterns are detected, falls back to regular chunking.
        """
        if not text or not text.strip():
            return []

        # Split into lines
        lines = text.split('\n')
        step_starts = []

        # Identify step boundaries
        for i, line in enumerate(lines):
            for pattern in self.STEP_PATTERNS:
                if re.match(pattern, line):
                    step_starts.append(i)
                    break

        # If no steps detected or too few, fall back to regular chunking
        if len(step_starts) < 2:
            logger.debug("No instruction pattern detected, using regular chunking")
            return super().chunk_text(text, metadata)

        logger.debug(f"Found {len(step_starts)} instruction steps")

        # Group lines into steps
        raw_steps = []
        for i, start_line in enumerate(step_starts):
            end_line = step_starts[i + 1] if i + 1 < len(step_starts) else len(lines)
            step_content = '\n'.join(lines[start_line:end_line]).strip()
            if step_content:
                raw_steps.append({
                    'content': step_content,
                    'start_line': start_line,
                    'end_line': end_line
                })

        # Optionally combine short steps
        if self.combine_short_steps:
            raw_steps = self._combine_short_steps(raw_steps)

        # Convert to Chunk objects
        chunks = []
        current_pos = 0

        for idx, step in enumerate(raw_steps):
            step_content = step['content']

            # Calculate character positions
            # This is approximate since we're working with lines
            start_char = text.find(step_content[:50]) if len(step_content) >= 50 else text.find(step_content)
            if start_char == -1:
                start_char = current_pos
            end_char = start_char + len(step_content)
            current_pos = end_char

            # Build metadata
            chunk_metadata = metadata.copy() if metadata else {}
            chunk_metadata['is_instruction_step'] = True
            chunk_metadata['step_number'] = idx + 1

            if len(step_content) >= self.min_chunk_size:
                chunks.append(Chunk(
                    content=step_content,
                    chunk_index=idx,
                    start_char=start_char,
                    end_char=end_char,
                    metadata=chunk_metadata
                ))

        # If combining resulted in too few chunks, just use regular chunking
        if len(chunks) < 2:
            return super().chunk_text(text, metadata)

        return chunks

    def _combine_short_steps(self, steps: List[Dict]) -> List[Dict]:
        """
        Combine consecutive short steps to reach target chunk size.
        """
        combined = []
        current_combined = None

        for step in steps:
            content = step['content']

            if current_combined is None:
                current_combined = {
                    'content': content,
                    'start_line': step['start_line'],
                    'end_line': step['end_line']
                }
            elif len(current_combined['content']) + len(content) + 2 <= self.chunk_size:
                # Combine with current
                current_combined['content'] += '\n\n' + content
                current_combined['end_line'] = step['end_line']
            else:
                # Save current and start new
                combined.append(current_combined)
                current_combined = {
                    'content': content,
                    'start_line': step['start_line'],
                    'end_line': step['end_line']
                }

        # Don't forget the last one
        if current_combined:
            combined.append(current_combined)

        return combined


def chunk_document(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    instruction_aware: bool = True,
    metadata: Optional[Dict[str, Any]] = None
) -> List[Chunk]:
    """
    Convenience function to chunk a document.

    Args:
        text: Document text to chunk
        chunk_size: Target chunk size in characters
        chunk_overlap: Overlap between chunks
        instruction_aware: Whether to use instruction-aware chunking
        metadata: Optional metadata to attach to chunks

    Returns:
        List of Chunk objects
    """
    if instruction_aware:
        chunker = InstructionAwareChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    else:
        chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    return chunker.chunk_text(text, metadata)
