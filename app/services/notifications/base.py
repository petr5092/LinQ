"""Public contract for custom messenger integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Optional, Tuple


class BaseMessengerAdapter(ABC):
    """Base class for messenger adapters registered with NotificationManager."""

    channel: ClassVar[str]
    enabled: bool = True

    def start(self) -> None:
        """Start background work such as a bot update poller, if needed."""

    def stop(self) -> None:
        """Stop background work started by this adapter."""

    @abstractmethod
    def send_alert(
        self,
        subscriber: dict,
        event: dict,
        snapshot_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Send one incident; return its remote message ID and message kind."""

    @abstractmethod
    def update_alert(self, delivery: dict, event: dict) -> None:
        """Update the previously sent message when the incident is merged or its status changes."""

    def is_gone(self, error: Exception) -> bool:
        """Return whether the error means this subscriber can no longer receive messages."""
        return False

    def info(self) -> dict:
        """Return a JSON-serializable health summary for the integration."""
        return {"configured": self.enabled, "status": "ready" if self.enabled else "disabled"}
