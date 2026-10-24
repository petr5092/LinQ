import os
import sys
import types
from unittest.mock import patch

import pytest

from app.services.notifications import BaseMessengerAdapter, NotificationManager
from app.services.notifications.extensions import load_adapter
from app.services.notifications.store import NotificationStore


class RecordingAdapter(BaseMessengerAdapter):
    channel = "company_chat"

    def __init__(self):
        self.sent = []
        self.updated = []
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def send_alert(self, subscriber, event, snapshot_path=None):
        self.sent.append((subscriber, event, snapshot_path))
        return "remote-message-1", "text"

    def update_alert(self, delivery, event):
        self.updated.append((delivery, event))

    def info(self):
        return {"configured": True, "status": "ready"}


@pytest.fixture
def manager(tmp_path):
    notification_manager = NotificationManager()
    notification_manager.store = NotificationStore(str(tmp_path / "notifications.db"))
    return notification_manager


def test_custom_adapter_receives_incidents_and_existing_message_updates(manager):
    adapter = RecordingAdapter()
    manager.register_adapter(adapter)
    subscriber = manager.store.upsert_subscriber(
        adapter.channel, "team-room", "Team room", "channel"
    )
    event = {"id": "incident-1", "severity": "high", "rule_label": "No helmet"}

    manager._deliver_incident(event)

    assert len(adapter.sent) == 1
    assert adapter.sent[0][0]["id"] == subscriber["id"]
    delivery = manager.store.get_deliveries_for_event("incident-1", adapter.channel)[0]
    assert delivery["message_id"] == "remote-message-1"

    update = {**event, "severity": "critical"}
    manager._refresh_incident_messages(update)
    assert adapter.updated == [(delivery, update)]
    assert manager.info()["channels"][adapter.channel]["status"] == "ready"


def test_custom_adapter_lifecycle_is_managed_by_notification_manager(manager):
    adapter = RecordingAdapter()
    manager.register_adapter(adapter)

    with patch.dict(os.environ, {"LINQ_MESSENGER_ADAPTERS": ""}):
        manager.start()
        try:
            assert adapter.started
        finally:
            manager.stop()

    assert adapter.stopped


def test_adapter_registration_validates_type_and_channel(manager):
    with pytest.raises(TypeError, match="BaseMessengerAdapter"):
        manager.register_adapter(object())

    class InvalidChannelAdapter(RecordingAdapter):
        channel = "Uppercase"

    with pytest.raises(ValueError, match="channel"):
        manager.register_adapter(InvalidChannelAdapter())

    manager.register_adapter(RecordingAdapter())
    with pytest.raises(ValueError, match="already registered"):
        manager.register_adapter(RecordingAdapter())


def test_configured_adapter_factory_is_loaded_before_start(manager):
    module = types.ModuleType("test_company_messenger_plugin")
    adapter = RecordingAdapter()
    module.create_adapter = lambda notification_manager: adapter

    with patch.dict(sys.modules, {module.__name__: module}), patch.dict(
        os.environ, {"LINQ_MESSENGER_ADAPTERS": f"{module.__name__}:create_adapter"}
    ):
        manager._load_configured_adapters()

    assert manager.adapters[adapter.channel] is adapter


def test_invalid_plugin_spec_fails_explicitly(manager):
    with patch.dict(os.environ, {"LINQ_MESSENGER_ADAPTERS": "missing_separator"}):
        with pytest.raises(ValueError, match="python.module:factory"):
            manager._load_configured_adapters()


def test_plugin_factory_must_return_adapter(manager):
    module = types.ModuleType("invalid_company_messenger_plugin")
    module.create_adapter = lambda notification_manager: object()

    with patch.dict(sys.modules, {module.__name__: module}):
        with pytest.raises(TypeError, match="must return a BaseMessengerAdapter"):
            load_adapter(f"{module.__name__}:create_adapter", manager)
