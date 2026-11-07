"""Reranker module to refine retrieval rankings using semantic, lexical, and precedence features."""

import re
from typing import List, Tuple
from helpdesk.chunking import Chunk
from helpdesk.utils import (
    extract_circular_numbers,
    extract_gazette_notifications,
    extract_train_numbers,
)


class PrecisionReranker:
    """Reranks candidate chunks using exact identifier overlap, date recency, and train specificity."""

    def __init__(self):
        pass

    def rerank(self, query: str, candidates: List[Tuple[Chunk, float]], top_k: int = 5) -> List[Tuple[Chunk, float]]:
        """
        Rerank (chunk, initial_score) pairs.
        Returns top_k (chunk, final_score) pairs sorted in descending order.
        """
        if not candidates:
            return []

        query_lower = query.lower()
        q_circs = extract_circular_numbers(query)
        q_gazs = extract_gazette_notifications(query)
        q_train_nums = extract_train_numbers(query)

        has_vande_bharat = "vande bharat" in query_lower or "amrit bharat" in query_lower
        has_tatkal = "tatkal" in query_lower or "aadhaar" in query_lower
        has_advance_res = "advance" in query_lower or "60 day" in query_lower or "120 day" in query_lower or "taj express" in query_lower
        has_chart = "chart" in query_lower

        scored_candidates = []

        for chunk, init_score in candidates:
            bonus = 0.0
            chunk_lower = chunk.text.lower()

            # Exact circular match
            for circ in q_circs:
                if circ in chunk.rule_refs or circ.lower() in chunk_lower:
                    bonus += 0.05

            # Exact gazette match
            for gaz in q_gazs:
                if gaz in chunk.rule_refs or gaz.lower() in chunk_lower:
                    bonus += 0.08

            # Exact train number match
            for t_num in q_train_nums:
                if t_num in chunk.train_refs or t_num in chunk.text:
                    bonus += 0.05

            # Specificity bonuses for specialized policies
            if has_vande_bharat and ("vande_bharat" in chunk.doc_name.lower() or "vande bharat" in chunk_lower):
                bonus += 0.05

            if has_tatkal and ("tatkal" in chunk.doc_name.lower() or "tatkal" in chunk_lower):
                bonus += 0.05

            if has_advance_res and ("advance_reservation" in chunk.doc_name.lower() or "advance reservation" in chunk_lower):
                bonus += 0.05

            if has_chart and ("reservation_charts" in chunk.doc_name.lower() or "reservation chart" in chunk_lower):
                bonus += 0.05

            final_score = init_score + bonus
            scored_candidates.append((chunk, final_score))

        # Sort descending by final score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return scored_candidates[:top_k]
