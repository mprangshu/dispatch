"""Chatbot orchestration — turn a message into a grounded reply.

Ties the pieces together (PROBLEM_STATEMENT.md sections 4.3-4.5):

1. Use ``router.py`` to detect intent (recommend / info / clarify).
2. Dispatch to the matching path via ``retriever.py``:
   * **recommend** — semantic search over agent summaries; return the best fit
     (or a shortlist) with a short explanation of why (section 4.3).
   * **info** — RAG: retrieve the relevant section chunk(s), pass them plus the
     question to the LLM, and answer grounded strictly in the retrieved text
     (section 4.4).
3. Handle edge cases (section 4.5): no match, ambiguous, out of scope, and
   strict grounding — say "I don't have that information" rather than guessing
   (e.g. Deployment fields that are "TBD", per section 8).

The LLM client is configurable (MODEL in ``config.py``) and used for intent
detection, answer generation, and recommendation explanations.
"""

# TODO: implement orchestration (intent -> path -> grounded reply) and the
# edge-case behavior, per PROBLEM_STATEMENT.md sections 4.3-4.5 and 6.4-6.5.
