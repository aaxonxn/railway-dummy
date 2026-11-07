"""Terminal User Interface for the Railway Passenger Help Desk."""

import json
import sys
from typing import Optional

from helpdesk import ask
from helpdesk.citations import format_citations_for_display


def display_response(res: dict) -> None:
    """Print response dictionary in a clean, passenger-friendly format."""
    print("\nAssistant:")
    print(res.get("answer", "").strip())

    sql = res.get("sql")
    if sql:
        print(f"\n[Timetable SQL Executed: {sql}]")

    sources = res.get("sources", [])
    if sources:
        print(f"\n{format_citations_for_display(sources)}")
    print()


def interactive_mode():
    """Run interactive terminal session for passengers."""
    print("==================================================")
    print("       RAILWAY PASSENGER HELP DESK                ")
    print("==================================================")
    print("Welcome! Ask me about railway policies,")
    print("ticket refunds, trains and timetables.")
    print("Type 'exit' or 'quit' to end.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nThank you for using Railway Passenger Help Desk.")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit", "q"]:
            print("\nThank you for using Railway Passenger Help Desk.")
            break

        res = ask(user_input)
        display_response(res)


def main():
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:]).strip()
        res = ask(question)
        display_response(res)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()

