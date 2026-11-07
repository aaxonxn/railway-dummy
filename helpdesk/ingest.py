"""Document ingestion and text extraction pipeline."""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional
import bs4
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

from helpdesk.config import config
from helpdesk.logging_config import logger
from helpdesk.ocr import ocr_pixmap, init_ocr
from helpdesk.utils import normalize_whitespace


# Document metadata mapped from official SOURCES.md
DOCUMENT_METADATA: Dict[str, Dict[str, str]] = {
    "indianrail_refund_rules_2015.html": {
        "title": "Revised Refund Rules w.e.f. 12.11.2015",
        "authority": "Indian Railways (indianrail.gov.in)",
        "date": "2015-11-12",
        "doc_type": "html",
        "scope": "Pre-revised vs revised refund rules, clerkage charges, cancellation timelines",
    },
    "irctc_refund_rules_jan2026.pdf": {
        "title": "Refund Rules and TDR Filing w.e.f. 12-NOVEMBER-2015 (Updated Jan 2026)",
        "authority": "IRCTC",
        "date": "2026-01-19",
        "doc_type": "pdf",
        "scope": "General IRCTC e-ticketing refund, cancellation charges, RAC/waitlist, TDR filing",
    },
    "rb_cc10_2024_advance_reservation.pdf": {
        "title": "Commercial Circular No. 10 of 2024: Time limit for Advance Reservations",
        "authority": "Railway Board, Ministry of Railways",
        "date": "2024-10-16",
        "doc_type": "pdf",
        "scope": "Reduction of Advance Reservation Period (ARP) from 120 to 60 days, exemptions (Taj/Gomti Express)",
    },
    "rb_cc08_2025_tatkal.pdf": {
        "title": "Commercial Circular No. 08 of 2025: Modification in Tatkal scheme",
        "authority": "Railway Board, Ministry of Railways",
        "date": "2025-06-10",
        "doc_type": "pdf",
        "scope": "Mandatory Aadhaar authentication for Tatkal bookings, identity verification rules",
    },
    "rb_cc10_2025_reservation_charts.pdf": {
        "title": "Commercial Circular No. 10 of 2025: Preparation of first reservation charts",
        "authority": "Railway Board, Ministry of Railways",
        "date": "2025-07-02",
        "doc_type": "pdf",
        "scope": "Timing and protocols for preparing first reservation charts",
    },
    "rb_cc08_2026_vande_bharat_sleeper_refund.pdf": {
        "title": "Commercial Circular No. 08 of 2026: Introduction of Vande Bharat Sleeper Express and Amrit Bharat II Express with rationalised refund provision",
        "authority": "Railway Board, Ministry of Railways",
        "date": "2026-01-19",
        "doc_type": "pdf",
        "scope": "Special refund rules, 72h/8h cancellation tiers, Gazette G.S.R. 41(E) for Vande Bharat Sleeper",
    },
    "pib_2026-03-24_reform_express.html": {
        "title": "Indian Railways Announces Five New Reforms Under 'Reform Express' (Release ID 2244597)",
        "authority": "Ministry of Railways via Press Information Bureau (PIB)",
        "date": "2026-03-24",
        "doc_type": "html",
        "scope": "Ticketing reforms, dynamic cancellation, passenger amenities",
    },
}


@dataclass
class ExtractedPage:
    """Represents text extracted from a single document page or HTML document."""

    doc_name: str
    page: Optional[int]  # 1-indexed for PDF, None for HTML
    text: str
    extraction_method: str  # 'pdf_text', 'pdf_ocr', 'html'
    title: str
    authority: str
    date: str
    doc_type: str
    char_count: int

    def to_dict(self) -> dict:
        return asdict(self)


def extract_table_as_markdown(table: bs4.element.Tag) -> str:
    """Convert an HTML <table> into clean Markdown format."""
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        row_text = [normalize_whitespace(cell.get_text()) for cell in cells]
        rows.append(row_text)

    if not rows:
        return ""

    # Normalize column count across all rows
    max_cols = max(len(r) for r in rows)
    if max_cols == 0:
        return ""

    norm_rows = [r + [""] * (max_cols - len(r)) for r in rows]

    lines = []
    # Header row
    lines.append("| " + " | ".join(norm_rows[0]) + " |")
    lines.append("| " + " | ".join(["---"] * max_cols) + " |")

    for r in norm_rows[1:]:
        lines.append("| " + " | ".join(r) + " |")

    return "\n" + "\n".join(lines) + "\n"


def extract_html_document(file_path: Path) -> List[ExtractedPage]:
    """Extract content from an HTML document preserving structure, headings, and tables."""
    doc_name = file_path.name
    meta = DOCUMENT_METADATA.get(doc_name, {
        "title": doc_name,
        "authority": "Official Railway Document",
        "date": "Unknown",
        "doc_type": "html",
        "scope": "Railway policy",
    })

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove non-content elements
    for el in soup(["script", "style", "noscript", "iframe"]):
        el.decompose()

    # Convert tables to markdown blocks before extracting general text
    for table in soup.find_all("table"):
        md_table = extract_table_as_markdown(table)
        table.replace_with(soup.new_string(md_table))

    # Extract text from main content or body
    body = soup.body if soup.body else soup
    text = body.get_text(separator="\n")
    cleaned_text = normalize_whitespace(text)

    page = ExtractedPage(
        doc_name=doc_name,
        page=None,
        text=cleaned_text,
        extraction_method="html",
        title=meta["title"],
        authority=meta["authority"],
        date=meta["date"],
        doc_type="html",
        char_count=len(cleaned_text),
    )
    return [page]


def extract_pdf_document(file_path: Path) -> List[ExtractedPage]:
    """Extract text from a PDF document page by page, invoking OCR for scanned pages."""
    doc_name = file_path.name
    meta = DOCUMENT_METADATA.get(doc_name, {
        "title": doc_name,
        "authority": "Official Railway Document",
        "date": "Unknown",
        "doc_type": "pdf",
        "scope": "Railway policy",
    })

    pages: List[ExtractedPage] = []
    ocr_initialized = False

    try:
        doc = fitz.open(str(file_path))
    except Exception as e:
        logger.error("Failed to open PDF %s: %s", file_path, e)
        return []

    for page_idx in range(len(doc)):
        page_num = page_idx + 1
        page = doc[page_idx]

        # Extract native text
        text = page.get_text()
        cleaned_text = normalize_whitespace(text)

        # Check if text is sparse (indicative of a scanned page)
        if len(cleaned_text) < config.ocr_min_text_chars:
            logger.info("Page %d of %s has only %d chars; initiating OCR...", page_num, doc_name, len(cleaned_text))
            if not ocr_initialized:
                init_ocr()
                ocr_initialized = True

            try:
                pix = page.get_pixmap(dpi=config.ocr_dpi)
                ocr_text = ocr_pixmap(pix, lang="eng")
                ocr_cleaned = normalize_whitespace(ocr_text)

                if len(ocr_cleaned) > len(cleaned_text):
                    cleaned_text = ocr_cleaned
                    method = "pdf_ocr"
                    logger.info("OCR successful on %s p.%d: extracted %d chars", doc_name, page_num, len(cleaned_text))
                else:
                    method = "pdf_text"
            except Exception as e:
                logger.error("OCR failed on %s p.%d: %s", doc_name, page_num, e)
                method = "pdf_text"
        else:
            method = "pdf_text"

        pages.append(
            ExtractedPage(
                doc_name=doc_name,
                page=page_num,
                text=cleaned_text,
                extraction_method=method,
                title=meta["title"],
                authority=meta["authority"],
                date=meta["date"],
                doc_type="pdf",
                char_count=len(cleaned_text),
            )
        )

    doc.close()
    return pages


def ingest_documents(documents_dir: Optional[Path] = None) -> List[ExtractedPage]:
    """Discover and ingest all PDF and HTML documents from the target directory."""
    dir_path = documents_dir or config.documents_dir
    if not dir_path.exists():
        logger.error("Documents directory does not exist: %s", dir_path)
        return []

    all_pages: List[ExtractedPage] = []
    files = sorted(dir_path.iterdir())

    for f in files:
        if f.suffix.lower() == ".pdf":
            logger.info("Ingesting PDF: %s", f.name)
            pages = extract_pdf_document(f)
            all_pages.extend(pages)
        elif f.suffix.lower() in [".html", ".htm"]:
            logger.info("Ingesting HTML: %s", f.name)
            pages = extract_html_document(f)
            all_pages.extend(pages)

    logger.info("Ingestion completed: extracted %d total pages across %d files", len(all_pages), len(files))
    return all_pages

