"""Intelligent question routing module directing queries to RAG, SQL, Hybrid, or Abstention."""

from enum import Enum
import re
from typing import Optional, Tuple
from helpdesk.logging_config import logger


class Route(str, Enum):
    RAG = "rag"
    SQL = "sql"
    HYBRID = "hybrid"
    ABSTAIN = "abstain"


# Keywords indicating information explicitly absent from the pack or out-of-scope
OUT_OF_SCOPE_PATTERNS = [
    r"\bhow\s+much\s+is\s+a\b.*\b(ticket|fare|price|cost)\b",
    r"\bfare\s+of\b",
    r"\bprice\s+of\s+(a\s+)?ticket\b",
    r"\bseat\s+availability\b",
    r"\b(berths?|seats?)\b.*\bavailable\b",
    r"\bberth\s+availability\b",
    r"\bpnr\s+(status|enquiry)\b",
    r"\blive\s+running\s+status\b",
    r"\bweather\b",
    r"\bstock\s+market\b",
    r"\bflight\b",
    r"\bhotel\b",
    r"\brecipe\b",
    r"\bwho\s+won\s+the\b",
]

# Mutation patterns that must be rejected / abstained
MUTATION_PATTERNS = [
    r"^\s*(delete|update|insert|drop|alter|create|truncate)\b",
    r"\b(change|update|delete|drop|insert|alter|modify|set|create)\b.*\b(departure|arrival|time|trains?|tables?|database)\b",
    r"\b(change|set)\s+the\s+departure\b",
]

# Timetable-specific keywords
TIMETABLE_PATTERNS = [
    r"\bwhich\s+trains?\s+(go|run|travel)\s+(from|between)\b",
    r"\btrains?\s+(from|between)\s+[A-Za-z\s()]+\s+(to|and)\s+[A-Za-z\s()]+",
    r"\bname\s+of\s+train\s+\d{5}\b",
    r"\btrain\s+\d{5}\s+is\s+called\b",
    r"\bwhat\s+is\s+train\s+\d{5}\b",
    r"\bhow\s+many\s+stops\b",
    r"\bintermediate\s+(halting\s+)?stations?\b",
    r"\bstation\s+code\b",
    r"\btrain\s+type\b",
    r"\bhow\s+many\s+(rajdhani|shatabdi|duronto|express)\s+trains\b",
    r"\bwhen\s+does\s+train\b",
    r"\bdeparture\s+time\b",
    r"\barrival\s+time\b",
    r"\bwhat\s+time\s+does\s+.*\s+(leave|arrive|depart)\b",
    r"\broute\s+of\s+train\b",
    r"\btimetable\b",
]

# Document policy keywords
POLICY_PATTERNS = [
    r"\brefund\b",
    r"\bcancellation\b",
    r"\bcancel\b",
    r"\btatkal\b",
    r"\baadhaar\b",
    r"\bclerkage\b",
    r"\bwaitlist\b",
    r"\bwaiting\s+list\b",
    r"\brac\b",
    r"\badvance\s+reservation\b",
    r"\barp\b",
    r"\bbooking\s+limit\b",
    r"\b60[- ]days?\b",
    r"\b120[- ]days?\b",
    r"\breservation\s+charts?\b",
    r"\bchart\s+preparation\b",
    r"\btdr\b",
    r"\bgazette\b",
    r"\bg\.?s\.?r\b",
    r"\bcircular\b",
    r"\bvande\s+bharat\s+sleeper\b",
]


def classify_question(question: str) -> Tuple[Route, str]:
    """
    Classify a passenger question into one of the four routes:
    - Route.ABSTAIN: out of scope, unsupported data (fares, PNR, live status), or mutations.
    - Route.HYBRID: requires both timetable information (e.g. train departure time) and policy documentation.
    - Route.SQL: pure timetable querying (train names, routes, stations, schedules).
    - Route.RAG: policy, refund, booking, cancellation, circular rules.
    """
    q_clean = question.strip()
    q_lower = q_clean.lower()

    # 1. Check for dangerous mutations
    for pattern in MUTATION_PATTERNS:
        if re.search(pattern, q_lower):
            logger.info("Routing '%s' -> ABSTAIN (mutation rejected)", q_clean)
            return Route.ABSTAIN, "I can't do that. I only run read-only queries on the timetable."

    # 2. Check for known out-of-scope / unsupported data (fares, seat availability, weather, etc.)
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, q_lower):
            logger.info("Routing '%s' -> ABSTAIN (out of scope)", q_clean)
            return Route.ABSTAIN, "I don't know. The pack has no fare tables, live running status, or seat availability data."

    # 3. Check for policy signals
    has_policy = any(re.search(p, q_lower) for p in POLICY_PATTERNS)

    # 4. Check for timetable signals
    has_timetable = any(re.search(p, q_lower) for p in TIMETABLE_PATTERNS)
    # Check if a 5-digit train number is present along with arrival/departure/station
    has_train_num = bool(re.search(r"\b\d{5}\b", q_clean))
    has_time_cue = bool(re.search(r"\b(leave|depart|arrive|departure|arrival|time|schedule|station|route|stop)\b", q_lower))

    if has_policy and (has_timetable or (has_train_num and has_time_cue)):
        logger.info("Routing '%s' -> HYBRID", q_clean)
        return Route.HYBRID, "Requires both timetable query and policy documentation."

    if has_timetable or (has_train_num and has_time_cue and not has_policy):
        logger.info("Routing '%s' -> SQL", q_clean)
        return Route.SQL, "Timetable query."

    if has_policy:
        logger.info("Routing '%s' -> RAG", q_clean)
        return Route.RAG, "Policy document query."

    # If question mentions stations or train number only
    if has_train_num or re.search(r"\b(express|rajdhani|shatabdi|train)\b", q_lower):
        logger.info("Routing '%s' -> SQL (train mention)", q_clean)
        return Route.SQL, "Timetable query."

    # Fallback to RAG if generally about railways, or ABSTAIN if completely unrelated
    if any(w in q_lower for w in ["railway", "train", "ticket", "passenger", "station", "board", "irctc"]):
        logger.info("Routing '%s' -> RAG (fallback)", q_clean)
        return Route.RAG, "General railway policy."

    logger.info("Routing '%s' -> ABSTAIN (unsupported query)", q_clean)
    return Route.ABSTAIN, "I could not find sufficient information in the supplied railway documents to answer this question reliably."
