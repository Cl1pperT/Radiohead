"""Meshtastic serial client wrapper."""

from __future__ import annotations

import glob
import inspect
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pubsub import pub

import meshtastic.serial_interface


BROADCAST_NUMS = {0, 0xFFFFFFFF}
BROADCAST_IDS = {"^all", "all", "broadcast"}


@dataclass
class InboundMessage:
    text: str
    sender_id: str
    sender_short_name: Optional[str]
    sender_long_name: Optional[str]
    channel: Optional[int]
    is_dm: bool
    rx_time: float
    raw: dict[str, Any]
    from_num: Optional[int]
    to_num: Optional[int]
    to_id: Optional[str]
    message_id: Optional[str]


class MeshtasticClient:
    def __init__(self, serial_port: Optional[str], baudrate: int, logger) -> None:
        self._serial_port = serial_port
        self._baudrate = baudrate
        self._logger = logger
        self._interface: Optional[meshtastic.serial_interface.SerialInterface] = None
        self._disconnect_event = threading.Event()
        self._on_message: Optional[Callable[[InboundMessage], None]] = None
        self._self_node_ids: set[str] = set()
        self._self_node_nums: set[int] = set()
        self._subscribed = False

    def connect(self) -> str:
        ports = [self._serial_port] if self._serial_port else self._autodetect_ports()
        if not ports:
            raise RuntimeError("No serial ports found for Meshtastic device")

        last_error: Optional[Exception] = None
        for port in ports:
            try:
                self._interface = self._create_interface(port)
                self._logger.info("Connected to Meshtastic", extra={"event": "connect", "port": port})
                self._refresh_self_ids()
                self._subscribe()
                return port
            except Exception as exc:  # pragma: no cover - hardware dependent
                last_error = exc
                self._logger.warning(
                    "Failed to connect to Meshtastic",
                    extra={"event": "connect_failed", "port": port, "error": str(exc)},
                )
                time.sleep(1)

        raise RuntimeError("Unable to connect to Meshtastic device") from last_error

    def _create_interface(self, port: str) -> meshtastic.serial_interface.SerialInterface:
        constructor = meshtastic.serial_interface.SerialInterface
        kwargs: dict[str, Any] = {"devPath": port}
        try:
            params = set(inspect.signature(constructor).parameters)
        except (TypeError, ValueError):
            params = set()

        if "baudRate" in params:
            kwargs["baudRate"] = self._baudrate
        elif "baudrate" in params:
            kwargs["baudrate"] = self._baudrate
        elif "baud" in params:
            kwargs["baud"] = self._baudrate

        try:
            return constructor(**kwargs)
        except TypeError:
            kwargs.pop("baudRate", None)
            kwargs.pop("baudrate", None)
            kwargs.pop("baud", None)
            return constructor(**kwargs)

    def close(self) -> None:
        if self._interface:
            try:
                self._interface.close()
            except Exception:  # pragma: no cover
                pass
        self._unsubscribe()
        self._interface = None
        self._disconnect_event.clear()
        self._subscribed = False

    def wait_for_disconnect(self) -> None:
        self._disconnect_event.wait()

    def register_message_callback(self, callback: Callable[[InboundMessage], None]) -> None:
        self._on_message = callback

    def send_text(
        self, text: str, destination_id: Optional[str | int], channel: Optional[int]
    ) -> None:
        if not self._interface:
            raise RuntimeError("Not connected")

        kwargs: dict[str, Any] = {}
        if destination_id:
            kwargs["destinationId"] = destination_id
        if channel is not None:
            kwargs["channelIndex"] = channel

        self._interface.sendText(text, **kwargs)

    def _subscribe(self) -> None:
        if self._subscribed:
            return
        pub.subscribe(self._on_receive, "meshtastic.receive")
        pub.subscribe(self._on_receive, "meshtastic.receive.text")
        pub.subscribe(self._on_disconnect, "meshtastic.connection.lost")
        pub.subscribe(self._on_disconnect, "meshtastic.connection.closed")
        pub.subscribe(self._on_disconnect, "meshtastic.connection.error")
        pub.subscribe(self._on_connect, "meshtastic.connection.established")
        self._subscribed = True

    def _unsubscribe(self) -> None:
        if not self._subscribed:
            return
        subscriptions = {
            "meshtastic.receive": self._on_receive,
            "meshtastic.receive.text": self._on_receive,
            "meshtastic.connection.lost": self._on_disconnect,
            "meshtastic.connection.closed": self._on_disconnect,
            "meshtastic.connection.error": self._on_disconnect,
            "meshtastic.connection.established": self._on_connect,
        }
        for topic, handler in subscriptions.items():
            try:
                pub.unsubscribe(handler, topic)
            except Exception:
                continue

    def _on_connect(self, interface: Any = None, **kwargs: Any) -> None:
        self._refresh_self_ids()

    def _on_disconnect(self, interface: Any = None, **kwargs: Any) -> None:
        self._logger.warning("Meshtastic disconnected", extra={"event": "disconnect"})
        self._disconnect_event.set()

    def _on_receive(
        self, packet: Optional[dict[str, Any]] = None, interface: Any = None, **kwargs: Any
    ) -> None:
        if packet is None:
            packet = kwargs.get("packet")
        if not isinstance(packet, dict):
            return
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(
                "Meshtastic packet received",
                extra={"event": "packet_raw", "packet": packet},
            )
        message = self._parse_packet(packet)
        if message and self._on_message:
            self._on_message(message)

    def _parse_packet(self, packet: dict[str, Any]) -> Optional[InboundMessage]:
        decoded = packet.get("decoded") or {}
        text = decoded.get("text")
        if not text:
            return None

        from_num = packet.get("from")
        from_id = packet.get("fromId")
        to_num = packet.get("to")
        to_id = packet.get("toId")
        channel = packet.get("channel")
        if channel is None:
            channel = packet.get("channelIndex")

        sender_id = from_id or (str(from_num) if from_num is not None else "unknown")
        is_dm = self._is_dm(to_num, to_id)
        rx_time = float(packet.get("rxTime") or time.time())

        sender_short, sender_long = self._lookup_sender_names(from_num, from_id)

        return InboundMessage(
            text=text,
            sender_id=sender_id,
            sender_short_name=sender_short,
            sender_long_name=sender_long,
            channel=channel,
            is_dm=is_dm,
            rx_time=rx_time,
            raw=packet,
            from_num=from_num,
            to_num=to_num,
            to_id=to_id,
            message_id=str(packet.get("id")) if packet.get("id") is not None else None,
        )

    def _lookup_sender_names(
        self, from_num: Optional[int], from_id: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        if not self._interface:
            return None, None
        node = None
        try:
            if from_num is not None and from_num in self._interface.nodes:
                node = self._interface.nodes.get(from_num)
            elif from_id and from_id in self._interface.nodes:
                node = self._interface.nodes.get(from_id)
        except Exception:
            node = None

        if not node:
            return None, None
        user = node.get("user", {}) if isinstance(node, dict) else {}
        return user.get("shortName"), user.get("longName")

    def _refresh_self_ids(self) -> None:
        if not self._interface:
            return
        try:
            info = self._interface.getMyNodeInfo()
            if info:
                node_num = info.get("myNodeNum") or info.get("nodeNum")
                node_id = info.get("myNodeId") or info.get("nodeId")
                if node_num is not None:
                    self._self_node_nums.add(int(node_num))
                if node_id:
                    self._self_node_ids.add(str(node_id))
        except Exception:
            pass

        try:
            if hasattr(self._interface, "localNode"):
                node_num = getattr(self._interface.localNode, "nodeNum", None)
                if node_num is not None:
                    self._self_node_nums.add(int(node_num))
                node_id = getattr(self._interface.localNode, "id", None)
                if node_id:
                    self._self_node_ids.add(str(node_id))
        except Exception:
            pass

    def is_from_self(self, message: InboundMessage) -> bool:
        if message.from_num is not None and message.from_num in self._self_node_nums:
            return True
        if message.sender_id in self._self_node_ids:
            return True
        return False

    @staticmethod
    def _autodetect_ports() -> list[str]:
        ports = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
        return sorted(ports)

    @staticmethod
    def _is_dm(to_num: Optional[int], to_id: Optional[str]) -> bool:
        if to_id and to_id.lower() not in BROADCAST_IDS:
            return True
        if to_num is not None and to_num not in BROADCAST_NUMS:
            return True
        return False
