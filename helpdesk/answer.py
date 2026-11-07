"""Grounded answer generation synthesizing retrieved evidence and SQL query results."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from helpdesk.chunking import Chunk
from helpdesk.citations import deduplicate_citations, validate_citation
from helpdesk.config import config
from helpdesk.llm import LLMClient
from helpdesk.logging_config import logger
from helpdesk.sql import SCHEMA_DOCUMENTATION, execute_sql, format_sql_results_as_text

RAG_SYSTEM_PROMPT = """You are the official Indian Railways Passenger Help Desk Assistant.
Answer the passenger's question using ONLY the provided official document excerpts.

STRICT OPERATIONAL RULES:
1. Base your answer strictly on the supplied document excerpts. Do NOT bring in external knowledge, unmentioned rules, or assumptions.
2. If the excerpts do not contain enough facts to answer the question completely and reliably, state clearly:
   "I could not find sufficient information in the supplied railway documents to answer this question reliably."
3. Exact identifiers matter: preserve train numbers, rule numbers, circular numbers (e.g. Commercial Circular No. 10 of 2024), gazette numbers (e.g. G.S.R. 41(E)), dates, refund percentages, and time windows.
4. When different documents mention differing rules:
   - Specific train rules (e.g. Vande Bharat Sleeper Express) supersede generic rules for that train type.
   - Newer Railway Board circulars supersede older rules on the same topic.
5. In your answer, do not invent citations. Mention the source document and page naturally if helpful.
"""

SQL_SYSTEM_PROMPT = f"""You are an expert SQLite query generator for the Indian Railways Timetable database (2016 snapshot).
Generate a single, read-only SELECT query to answer the passenger question.

{SCHEMA_DOCUMENTATION}

RULES:
1. Output ONLY the raw SQL query. Do not wrap in markdown quotes (no ```sql). Do not add explanations.
2. The query MUST be a SELECT statement. NEVER use INSERT, UPDATE, DELETE, DROP, ALTER, PRAGMA, or ATTACH.
3. Train numbers are text strings: e.g. number = '12430', number = '12002'.
4. To find trains from station A to station B, join the 'stops' view to itself:
   SELECT t.number, t.name, a.departure, b.arrival
   FROM stops a
   JOIN stops b ON b.train_number = a.train_number AND b.stop_sequence > a.stop_sequence
   JOIN trains t ON t.number = a.train_number
   WHERE a.station_code = 'JP' AND b.station_code = 'UDZ'
   ORDER BY a.departure;
5. For station names, use UPPER() and LIKE: e.g. UPPER(name) LIKE '%DELHI%'.
6. If the question cannot be answered from the database schema (e.g. fares, seat availability, PNR, live status), output: NONE.
"""


class AnswerGenerator:
    """Coordinates answer synthesis for RAG, SQL, and Hybrid routes."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def generate_rag_answer(self, question: str, chunks: List[Chunk]) -> Tuple[str, List[Dict[str, Any]], bool]:
        """
        Synthesize answer from retrieved chunks.
        Returns (answer_text, sources, dont_know).
        """
        if not chunks:
            return (
                "I could not find sufficient information in the supplied railway documents to answer this question reliably.",
                [],
                True,
            )

        # Build context
        context_blocks = []
        sources = []
        for i, c in enumerate(chunks, 1):
            page_str = f"Page {c.page}" if c.page is not None else "Page null"
            context_blocks.append(
                f"[Source {i}: doc={c.doc_name}, page={c.page}, title='{c.title}', date='{c.date}']\n{c.text}\n"
            )
            sources.append({"doc": c.doc_name, "page": c.page})

        context_text = "\n".join(context_blocks)
        prompt = f"""Passenger Question: {question}

Official Document Excerpts:
{context_text}

Provide a concise, accurate, passenger-friendly answer based solely on the excerpts above.
If the excerpts do not contain the answer, say "I could not find sufficient information in the supplied railway documents to answer this question reliably."
"""

        try:
            raw_answer = self.llm.generate(prompt=prompt, system_instruction=RAG_SYSTEM_PROMPT)
            answer = raw_answer.strip()
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            # Fallback deterministic grounded extraction
            answer = f"According to the official railway records ({chunks[0].doc_name}): {chunks[0].text[:300]}..."

        # Check for abstention signals
        dont_know = False
        lower_ans = answer.lower()
        if "could not find sufficient information" in lower_ans or "not mentioned in the" in lower_ans or "i don't know" in lower_ans:
            dont_know = True
            sources = []
        else:
            sources = deduplicate_citations(sources)

        return answer, sources, dont_know

    def generate_sql_query(self, question: str) -> Optional[str]:
        """Generate SQL query string using Gemini."""
        prompt = f"Passenger Question: {question}\nGenerate SQL:"
        try:
            sql_resp = self.llm.generate(prompt=prompt, system_instruction=SQL_SYSTEM_PROMPT)
            cleaned = sql_resp.strip()
            # Clean markdown codeblocks if model included them
            cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

            if cleaned.upper() == "NONE" or not cleaned:
                return None
            return cleaned
        except Exception as e:
            logger.error("Failed to generate SQL with LLM: %s", e)
            return None

    def generate_sql_answer(self, question: str, sql_query: Optional[str] = None) -> Tuple[str, Optional[str], bool]:
        """
        Generate SQL query, execute it, and synthesize answer.
        Returns (answer_text, executed_sql, dont_know).
        """
        query = sql_query or self.generate_sql_query(question)
        if not query:
            return "I don't know. The pack has no records to answer this timetable query.", None, True

        ok, rows, executed_query, err = execute_sql(query)
        if not ok or err:
            logger.warning("SQL execution failed: %s", err)
            return f"I could not query the timetable database: {err}", executed_query, True

        if not rows:
            return "No matching timetable records were found in the database.", executed_query, False

        # Format answer using LLM or structured formatter
        results_str = format_sql_results_as_text(rows)
        synthesis_prompt = f"""Passenger Question: {question}
Executed SQL: {executed_query}
Query Results:
{results_str}

Summarize this into a clear, direct, passenger-friendly answer. Mention train numbers, names, and times as found in the results.
"""
        try:
            answer = self.llm.generate(prompt=synthesis_prompt)
            return answer.strip(), executed_query, False
        except Exception:
            return f"According to the timetable database:\n{results_str}", executed_query, False

    def generate_hybrid_answer(
        self, question: str, chunks: List[Chunk], sql_query: Optional[str] = None
    ) -> Tuple[str, List[Dict[str, Any]], Optional[str], bool]:
        """
        Synthesize answer requiring both timetable database query and document evidence.
        Returns (answer_text, sources, sql, dont_know).
        """
        # 1. Execute SQL
        query = sql_query or self.generate_sql_query(question)
        sql_results_text = "No database query executed."
        executed_sql = None
        if query:
            ok, rows, exec_q, err = execute_sql(query)
            if ok and not err:
                executed_sql = exec_q
                sql_results_text = format_sql_results_as_text(rows)

        # 2. Gather Document Context
        context_blocks = []
        sources = []
        for i, c in enumerate(chunks, 1):
            context_blocks.append(f"[Source {i}: doc={c.doc_name}, page={c.page}]\n{c.text}\n")
            sources.append({"doc": c.doc_name, "page": c.page})
        doc_context = "\n".join(context_blocks)

        prompt = f"""Passenger Question: {question}

Timetable Database Query ({executed_sql}):
{sql_results_text}

Document Excerpts:
{doc_context}

Provide a complete, passenger-friendly answer addressing both the timetable facts (train times/departure) and the policy/cancellation rules from the excerpts.
"""
        try:
            answer = self.llm.generate(prompt=prompt, system_instruction=RAG_SYSTEM_PROMPT)
            sources = deduplicate_citations(sources)
            return answer.strip(), sources, executed_sql, False
        except Exception as e:
            logger.error("Hybrid generation failed: %s", e)
            fallback = f"Timetable: {sql_results_text}\nPolicy: According to {chunks[0].doc_name} (Page {chunks[0].page}): {chunks[0].text[:200]}..."
            return fallback, deduplicate_citations(sources), executed_sql, False

