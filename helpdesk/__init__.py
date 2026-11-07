"""Railway Passenger Help Desk Package."""

__version__ = "1.0.0"

def ask(question: str) -> dict:
    """Central entry point for answering railway passenger questions."""
    from helpdesk.pipeline import ask as _ask
    return _ask(question)

__all__ = ["ask"]

