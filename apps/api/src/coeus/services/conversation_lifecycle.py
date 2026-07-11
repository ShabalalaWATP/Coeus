"""Deterministic intake-conversation lifecycle.

Decides when the chat ends. All decisions and copy here are local and
deterministic; the LLM is never asked whether the conversation is complete.

States (stored on ``TicketRecord.conversation_status``):
- ``open``: normal elicitation.
- ``close_offered``: the intake is complete and the assistant has asked
  whether there is anything else to add.
- ``closed``: the customer confirmed; the chat takes no further messages.
"""

import re

CONVERSATION_OPEN = "open"
CONVERSATION_CLOSE_OFFERED = "close_offered"
CONVERSATION_CLOSED = "closed"

# Customer phrases that mean "I want to finish here". Matched on a
# whitespace-normalised, casefolded message with apostrophes stripped.
END_INTENT_CUES = (
    "thats all",
    "that is all",
    "thats everything",
    "that is everything",
    "nothing else",
    "nothing more",
    "all done",
    "im done",
    "i am done",
    "were done",
    "we are done",
    "end chat",
    "end the chat",
    "lets finish",
    "finish here",
    "finish now",
    "finish up",
    "submit it",
    "go ahead and submit",
    "please submit",
)

# Short confirmations that close the chat once a close has been offered. A
# bare "yes" is ambiguous for the offer question ("anything else to add, or
# shall we finish?") so it deliberately does not close; the offer repeats.
CLOSE_CONFIRMATIONS = frozenset(
    {"no", "nope", "no thanks", "no thank you", "nothing", "none", "yes finish", "yes please"}
)

CLOSE_OFFER_MESSAGE = (
    "I think I have everything I need. Is there anything else you would like "
    "to add, or shall we finish here?"
)
CLOSED_MESSAGE = (
    "Thank you, that completes the intake. Review the details and press "
    "Submit when you are ready; I will check existing reporting first."
)


def wants_to_end(message: str) -> bool:
    normalised = _normalise(message)
    return any(cue in normalised for cue in END_INTENT_CUES)


def confirms_close(message: str) -> bool:
    """After a close offer, a short no/none reply or an end request closes."""
    normalised = _normalise(message)
    return normalised in CLOSE_CONFIRMATIONS or wants_to_end(message)


def cannot_close_message(next_question: str) -> str:
    return f"Before this can be submitted I still need a little more information. {next_question}"


def _normalise(message: str) -> str:
    stripped = re.sub("[\u2019']", "", message)
    stripped = re.sub(r"[^a-z0-9 ]", " ", stripped.casefold())
    return " ".join(stripped.split())
