"""CLI entry point — interactive REPL over the chatbot.

The first version is CLI-only; the core logic stays in ``src/`` and decoupled
from this interface so a web/API front end can be added later
(PROBLEM_STATEMENT.md sections 6.7 and 7). Two subcommands:

* ``python app.py``        — start the interactive chat REPL.
* ``python app.py index``  — (re)build the ChromaDB store from ``agents/``
                             (a convenience wrapper over ``python -m src.index``).

The REPL checks the store exists first and points you at ``index`` if it
doesn't, so a fresh clone gets a clear next step instead of a stack trace.
"""

from __future__ import annotations

import argparse
import sys

from src import config, index
from src.chatbot import handle

_BANNER = (
    "Agent Recommender & Q&A Chatbot\n"
    "Describe a task to get an agent recommendation, or ask about a specific "
    "agent. Type 'exit' (or Ctrl-D) to quit.\n"
)

_PROMPT = "you> "
_EXIT_WORDS = {"exit", "quit", ":q"}


def build_index() -> None:
    """Build the Chroma store and print a short summary."""
    stats = index.build_index()
    print(
        f"Indexed {stats['agents']} agents -> "
        f"{stats['summary_records']} summary + {stats['section_records']} section "
        f"records at {stats['chroma_path']}"
    )


def _store_ready() -> bool:
    """True when both collections exist (i.e. the catalog has been indexed)."""
    try:
        client = index.get_client()
        index.get_summary_collection(client)
        index.get_section_collection(client)
        return True
    except Exception:
        return False


def repl() -> None:
    """Run the interactive chat loop until EOF / an exit word."""
    if not _store_ready():
        print(
            "The catalog isn't indexed yet. Build it first with:\n"
            "    python app.py index\n",
            file=sys.stderr,
        )
        return

    print(_BANNER)
    while True:
        try:
            message = input(_PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()  # leave the terminal on a clean line
            break

        message = message.strip()
        if not message:
            continue
        if message.casefold() in _EXIT_WORDS:
            break

        print(f"\n{handle(message)}\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="app.py",
        description="Agent Recommender & Q&A Chatbot (CLI).",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("index", help="(re)build the ChromaDB store from agents/")
    sub.add_parser("chat", help="start the interactive chat REPL (default)")

    args = parser.parse_args(argv)

    if args.command == "index":
        build_index()
    else:  # default (no subcommand) or explicit "chat"
        repl()


if __name__ == "__main__":
    main()
