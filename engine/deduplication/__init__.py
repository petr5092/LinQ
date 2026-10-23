"""
Пакет дедупликации инцидентов и подавления ложных тревог (Anti-Spam) LinQ Safety Guard.
"""

from engine.deduplication.anti_spam import AntiSpamEngine
from engine.deduplication.types import ConfirmedIncident, IncidentState

__all__ = [
    "AntiSpamEngine",
    "ConfirmedIncident",
    "IncidentState",
]
