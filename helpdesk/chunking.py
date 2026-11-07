"""Document chunking with table preservation, structural boundaries, and metadata tagging."""

from dataclasses import dataclass, asdict
import re
from typing import List, Optional
from helpdesk.config import config
from helpdesk.ingest import ExtractedPage
from helpdesk.utils import (
    normalize_whitespace,
    extract_circular_numbers,
    extract_gazette_notifications,
    extract_train_numbers,
)


@dataclass
class Chunk:
    """Represents a coherent text chunk for indexing and retrieval."""

    chunk_id: str
    doc_name: str
    page: Optional[int]  # 1-indexed for PDF, None for HTML
    text: str
    title: str
    authority: str
    date: str
    doc_type: str
    is_table: bool
    rule_refs: List[str]
    train_refs: List[str]
    section_header: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def detect_train_names(text: str) -> List[str]:
    """Identify specific train names or classes mentioned in the text."""
    train_names = [
        "Vande Bharat Sleeper",
        "Vande Bharat",
        "Amrit Bharat",
        "Rajdhani",
        "Shatabdi",
        "Duronto",
        "Garib Rath",
        "Jan Shatabdi",
        "Taj Express",
        "Gomti Express",
        "Reform Express",
    ]
    found = []
    text_lower = text.lower()
    for name in train_names:
        if name.lower() in text_lower:
            found.append(name)
    return found


def extract_section_headers(text: str) -> Optional[str]:
    """Extract candidate section heading or subject line."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for line in lines[:5]:
        if re.match(r"^(Sub|Subject|Ref|Reference|Commercial Circular|Rule\s+\d+|[0-9]+\.\s+[A-Z])", line, re.IGNORECASE):
            return line[:120]
    return None


def split_text_preserving_tables(text: str, max_chunk_size: int = 800, overlap: int = 150) -> List[tuple[str, bool]]:
    """
    Split text into logical blocks preserving tables intact.
    Returns a list of (block_text, is_table).
    """
    blocks: List[tuple[str, bool]] = []
    lines = text.split("\n")
    current_lines: List[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        is_table_row = stripped.startswith("|") and stripped.endswith("|")

        if is_table_row:
            if not in_table:
                # Flush previous non-table lines if any
                if current_lines:
                    block_text = normalize_whitespace("\n".join(current_lines))
                    if block_text:
                        blocks.append((block_text, False))
                    current_lines = []
                in_table = True
            current_lines.append(line)
        else:
            if in_table:
                # Flush table block
                if current_lines:
                    block_text = "\n".join(current_lines).strip()
                    if block_text:
                        blocks.append((block_text, True))
                    current_lines = []
                in_table = False
            current_lines.append(line)

    # Flush remaining lines
    if current_lines:
        block_text = "\n".join(current_lines).strip() if in_table else normalize_whitespace("\n".join(current_lines))
        if block_text:
            blocks.append((block_text, in_table))

    # Second pass: for non-table blocks that exceed max_chunk_size, split by paragraphs
    refined_blocks: List[tuple[str, bool]] = []
    for content, is_tbl in blocks:
        if is_tbl or len(content) <= max_chunk_size:
            refined_blocks.append((content, is_tbl))
        else:
            # Paragraph split
            paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
            chunk_buffer = ""
            for p in paragraphs:
                if len(chunk_buffer) + len(p) + 2 <= max_chunk_size:
                    chunk_buffer = f"{chunk_buffer}\n\n{p}" if chunk_buffer else p
                else:
                    if chunk_buffer:
                        refined_blocks.append((chunk_buffer, False))
                    if len(p) > max_chunk_size:
                        # Fallback sliding window on sentences
                        sentences = re.split(r"(?<=[.!?])\s+", p)
                        s_buf = ""
                        for s in sentences:
                            if len(s_buf) + len(s) + 1 <= max_chunk_size:
                                s_buf = f"{s_buf} {s}" if s_buf else s
                            else:
                                if s_buf:
                                    refined_blocks.append((s_buf, False))
                                s_buf = s
                        if s_buf:
                            chunk_buffer = s_buf
                        else:
                            chunk_buffer = ""
                    else:
                        chunk_buffer = p
            if chunk_buffer:
                refined_blocks.append((chunk_buffer, False))

    return refined_blocks


def chunk_page(page: ExtractedPage) -> List[Chunk]:
    """Chunk a single ExtractedPage into one or more Chunk objects."""
    if not page.text.strip():
        return []

    # Get blocks
    blocks = split_text_preserving_tables(
        page.text,
        max_chunk_size=config.chunk_size_chars,
        overlap=config.chunk_overlap_chars,
    )

    chunks: List[Chunk] = []
    page_tag = f"p{page.page}" if page.page is not None else "pNone"
    clean_doc = re.sub(r"[^a-zA-Z0-9_]", "_", page.doc_name.replace(".pdf", "").replace(".html", ""))

    for idx, (block_text, is_tbl) in enumerate(blocks):
        if not block_text.strip():
            continue

        chunk_id = f"{clean_doc}_{page_tag}_c{idx}"

        # Extract rule references
        circ_refs = extract_circular_numbers(block_text)
        gaz_refs = extract_gazette_notifications(block_text)
        rule_nums = re.findall(r"\bRule\s+\d+\b", block_text, re.IGNORECASE)
        rule_refs = list(dict.fromkeys(circ_refs + gaz_refs + rule_nums))

        # Extract train references
        train_nums = extract_train_numbers(block_text)
        train_names = detect_train_names(block_text)
        train_refs = list(dict.fromkeys(train_nums + train_names))

        section_hdr = extract_section_headers(block_text)

        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                doc_name=page.doc_name,
                page=page.page,
                text=block_text,
                title=page.title,
                authority=page.authority,
                date=page.date,
                doc_type=page.doc_type,
                is_table=is_tbl,
                rule_refs=rule_refs,
                train_refs=train_refs,
                section_header=section_hdr,
            )
        )

    return chunks


def chunk_all_pages(pages: List[ExtractedPage]) -> List[Chunk]:
    """Chunk all extracted pages from all documents."""
    all_chunks: List[Chunk] = []
    for page in pages:
        page_chunks = chunk_page(page)
        all_chunks.extend(page_chunks)
    return all_chunks

