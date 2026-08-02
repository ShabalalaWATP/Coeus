"""Bound chat history before persistence or provider acquisition."""

from coeus.core.errors import AppError
from coeus.core.resource_limits import text_bytes
from coeus.domain.tickets import TicketRecord


def chat_bytes(ticket: TicketRecord) -> int:
    return sum(text_bytes(item.body) for item in ticket.messages)


def ensure_chat_budget(
    ticket: TicketRecord,
    message: str,
    *,
    max_messages: int,
    max_history_bytes: int,
    max_reply_bytes: int,
) -> None:
    if len(ticket.messages) + 2 > max_messages:
        raise AppError(409, "chat_history_limit_reached", "The chat history limit was reached.")
    projected = chat_bytes(ticket) + text_bytes(message) + max_reply_bytes
    if projected > max_history_bytes:
        raise AppError(409, "chat_history_limit_reached", "The chat history limit was reached.")
