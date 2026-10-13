"""Диалог с пользователем: конечный автомат (idle -> screening -> review -> document_generation -> completed) и анкета."""

from .intents import detect_intent, parse_command
from .machine import DialogMachine, Reply
from .questions import QUESTIONS, question_order
from .state import COMPLETED, DOCUMENT_GENERATION, IDLE, REVIEW, SCREENING, STATES, DialogContext

__all__ = [
    "DialogMachine", "Reply", "DialogContext", "QUESTIONS", "question_order", "detect_intent", "parse_command",
    "IDLE", "SCREENING", "REVIEW", "DOCUMENT_GENERATION", "COMPLETED", "STATES",
]
