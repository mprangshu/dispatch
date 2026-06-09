"""Intent router — classify each incoming message before routing it.

Classifies a user message into one of three intents
(PROBLEM_STATEMENT.md section 4.2):

* ``recommend`` — the user describes a need and wants a fitting agent.
* ``info`` — the user asks a question about a specific agent.
* ``clarify`` — the message is too vague to act on.

Pure classification only; the actual recommendation / RAG paths are dispatched
by ``chatbot.py``.
"""

# TODO: implement intent detection returning one of recommend|info|clarify,
# per PROBLEM_STATEMENT.md sections 4.2 and 6.6.
