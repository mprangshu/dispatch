"""CLI entry point — interactive REPL over the chatbot.

The first version is CLI-only; the core logic stays in ``src/`` and decoupled
from this interface so a web/API front end can be added later
(PROBLEM_STATEMENT.md sections 6.7 and 7).
"""

# TODO: wire up a CLI loop that reads a user message, routes it through
# src.chatbot, and prints the grounded reply, per PROBLEM_STATEMENT.md
# section 6.7. (Consider an `index` subcommand to (re)build the Chroma store.)


def main() -> None:
    # TODO: implement the CLI per PROBLEM_STATEMENT.md section 6.7.
    raise NotImplementedError


if __name__ == "__main__":
    main()
