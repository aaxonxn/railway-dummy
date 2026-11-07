# Railway Passenger Help Desk — 10-Minute Capstone Demonstration Guide

This guide outlines a polished, step-by-step 10-minute presentation and demonstration for evaluators and technical reviewers.

---

## Demonstration Script & Timeline (10 Minutes)

| Time | Segment | Action / Demonstration | Key Talking Points |
|---|---|---|---|
| **00:00 - 01:00** | **1. Problem Introduction** | Show terminal and repository layout. | Explain the challenge: Indian Railways rules change frequently, circulars supersede older policies, and timetables are structured across relational databases. Hallucinations are unacceptable. |
| **01:00 - 02:00** | **2. Architecture Walkthrough** | Reference system architecture diagram in README. | Explain the four pathways: Document RAG, Timetable SQL, Hybrid, and Abstention. Emphasize the mandatory 4-key contract (`answer`, `sources`, `sql`, `dont_know`). |
| **02:00 - 03:00** | **3. Ingestion & Selective OCR** | Run `python build_index.py --stats` and inspect scanned pages. | Explain why selective OCR is used: 18 pages contain extractable digital text; 8 pages are scanned images (e.g. Circular 10/2024, 10/2025). Only scanned pages are routed to Tesseract 5.4. |
| **03:00 - 04:30** | **4. Document Policy Query (RAG)** | Run: `python ask.py "What is the cancellation charge on a confirmed Vande Bharat Sleeper ticket 10 hours before departure?"` | Demonstrate that the system retrieves the specialized 2026 circular (`rb_cc08_2026...`), quotes the exact 50% charge, and cites Page 5. |
| **04:30 - 05:30** | **5. Timetable Query (SQL)** | Run: `python ask.py "What is the name of train 12430?"` | Show safe Natural-Language-to-SQL generation (`SELECT name FROM trains WHERE number = '12430'`), read-only execution, and passenger-friendly output. |
| **05:30 - 06:30** | **6. Hybrid Query (SQL + RAG)** | Run: `python ask.py "When does the Bhopal Shatabdi (12002) leave New Delhi, and what is the cancellation charge if I cancel my confirmed AC chair car ticket 5 days before?"` | Show simultaneous timetable query execution (`departure: 06:15`) combined with document retrieval (flat cancellation fee of Rs 180 + GST), citing both SQL and document sources. |
| **06:30 - 07:30** | **7. Reliable Abstention & Safety** | Run: `python ask.py "How much is a 3AC ticket on the Mumbai Rajdhani from Mumbai to Delhi?"` followed by `python ask.py "Change the departure time of train 12002 to 07:00 in your database."` | Show that the system detects missing fare data and mutation instructions, outputting `dont_know: True` with clear passenger explanation. |
| **07:30 - 08:30** | **8. Exact Citations & Page Verification** | Point out the source metadata in responses. | Verify that cited pages match the original PDF pages and HTML citations have `page: null`. |
| **08:30 - 09:30** | **9. Evaluation Suite & Metrics** | Run: `python eval/evaluate.py --retrieval-only` | Show benchmark results: **Hit@1 = 100.0%**, **Hit@3 = 100.0%**, **Hit@5 = 100.0%**, **MRR = 1.0000**, and **Routing Accuracy = 100.0%**. |
| **09:30 - 10:00** | **10. Conclusion & Q&A** | Run: `pytest -v` | Conclude with 43 passing automated tests and open the floor for evaluator questions. |

---

## Frequently Asked Questions & Technical Responses

### Q1: How does the system handle conflicting rules across different circulars?
**Answer**:  
The system implements a hierarchical precedence strategy based on document dates, issuing authority, and service specificity. For example:
- Commercial Circular No. 08 of 2026 contains specialized refund rules specifically enacted for Vande Bharat Sleeper Express.
- The retrieval reranker recognizes the train specificity in the query and boosts the 2026 circular chunks above generic 2015 refund rules.
- When no specific exemption exists, the newer Railway Board circular takes precedence over older rules on identical topics.

### Q2: How is SQL injection prevented if Gemini generates the SQL query?
**Answer**:  
We employ a multi-layered defense-in-depth model:
1. **Read-Only SQLite Connection**: Opened using `file:...mode=ro`.
2. **SQLite Authorizer Callback**: Low-level hook registered on the connection that allows only `SQLITE_SELECT`, `SQLITE_READ`, and `SQLITE_FUNCTION`. Any mutation attempt (like `SQLITE_INSERT` or `SQLITE_DROP_TABLE`) raises an immediate execution error.
3. **AST / Regex Validator**: Queries are checked to ensure they start with `SELECT` or `WITH`, contain no SQL comments (`--`, `/*`), contain no semicolons (multiple statements), and reference only legitimate timetable tables (`stations`, `train_types`, `trains`, `schedules`, `stops`).
4. **Row Limit Injection**: If the query lacks a LIMIT clause, `LIMIT 50` is automatically appended to protect memory.

### Q3: Why use Reciprocal Rank Fusion (RRF) instead of pure dense embeddings?
**Answer**:  
Dense semantic embeddings excel at understanding broad concepts (such as "booking horizons" matching "advance reservation period"), but they struggle with exact statutory identifiers like circular numbers (`Commercial Circular No. 10 of 2024`), train numbers (`12430`), or gazette IDs (`G.S.R. 41(E)`). BM25 provides pinpoint lexical accuracy on exact identifiers, while dense embeddings provide conceptual recall. Combining them via RRF ($k=60$) yielded 100% Hit@1, compared to 81.8% for BM25 alone and 90.9% for dense search alone.

### Q4: Why are some pages extracted with OCR while others use digital text extraction?
**Answer**:  
Digital text extraction via PyMuPDF is orders of magnitude faster and yields cleaner text. However, two Railway Board circulars (10/2024 and 10/2025) and pages 3–6 of Circular 08/2025 are scanned image documents without an embedded text layer. Our pipeline inspects extracted character count per page: pages with fewer than 50 characters automatically trigger Tesseract OCR with image contrast enhancement, while digital pages are parsed instantly.

### Q5: What happens if the Gemini API experiences network errors or quota limits?
**Answer**:  
The `LLMClient` incorporates exponential backoff retries and automatic model failover between `gemini-3-flash-preview` and `gemini-3.1-flash-lite`. If an API outage occurs, the pipeline catches the exception, logs it securely with credential masking, and provides a deterministic evidence-grounded fallback rather than crashing.

