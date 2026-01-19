"""Main entrypoint for the Meshtastic LLM bridge."""

from __future__ import annotations

import logging
import time
from typing import Optional

from .config import Settings, load_settings
from .meshtastic_client import InboundMessage, MeshtasticClient
from .ollama_client import OllamaClient
from .prompt import (
    build_prompt,
    chunk_text,
    enforce_max_length,
    normalize_reply,
    strip_trigger_prefix,
)
from .storage import MessageRecord, SQLiteStorage, now_ts
from .utils.logging import configure_logging, log_event


class BridgeService:
    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self._settings = settings
        self._logger = logger
        self._storage = SQLiteStorage(settings.data_dir)
        self._ollama = OllamaClient(
            host=settings.ollama_host,
            model=settings.ollama_model,
        )
        self._client: Optional[MeshtasticClient] = None

    def run_forever(self) -> None:
        backoff = 2.0
        while True:
            self._client = MeshtasticClient(
                serial_port=self._settings.serial_port,
                baudrate=self._settings.baudrate,
                logger=self._logger,
            )
            self._client.register_message_callback(self._handle_message)
            try:
                port = self._client.connect()
                log_event(self._logger, logging.INFO, "listening", port=port)
                backoff = 2.0
                self._client.wait_for_disconnect()
            except KeyboardInterrupt:
                log_event(self._logger, logging.INFO, "shutdown")
                break
            except Exception as exc:  # pragma: no cover
                log_event(
                    self._logger,
                    logging.ERROR,
                    "bridge_error",
                    error=str(exc),
                )
            finally:
                self._client.close()

            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

        self._storage.close()

    def _handle_message(self, message: InboundMessage) -> None:
        try:
            if self._client and self._client.is_from_self(message):
                log_event(
                    self._logger,
                    logging.DEBUG,
                    "ignore_self",
                    sender_id=message.sender_id,
                )
                return

            history = self._storage.get_recent_messages(
                message.sender_id,
                limit=self._settings.memory_turns * 2,
            )

            stored_text = strip_trigger_prefix(message.text, self._settings.trigger_prefix)
            inbound_record = MessageRecord(
                direction="in",
                sender_id=message.sender_id,
                sender_short_name=message.sender_short_name,
                sender_long_name=message.sender_long_name,
                channel=message.channel,
                text=stored_text,
                timestamp=message.rx_time,
                latency_ms=None,
                message_id=message.message_id,
            )
            self._storage.add_message(inbound_record)

            log_event(
                self._logger,
                logging.INFO,
                "message_in",
                sender_id=message.sender_id,
                channel=message.channel,
                is_dm=message.is_dm,
                text=message.text,
                rx_time=message.rx_time,
                rx_age_ms=round((now_ts() - message.rx_time) * 1000, 2),
            )

            if not self._should_respond(message):
                return

            stripped_text = strip_trigger_prefix(message.text, self._settings.trigger_prefix)
            if not stripped_text:
                log_event(self._logger, logging.INFO, "empty_trigger", sender_id=message.sender_id)
                return
            message.text = stripped_text
            prompt = build_prompt(
                message=message,
                history=history,
                max_reply_chars=self._settings.max_reply_chars,
            )

            llm_result = self._ollama.generate(prompt)
            reply = normalize_reply(llm_result.response)
            reply = enforce_max_length(reply, self._settings.max_reply_chars)

            if not reply:
                log_event(self._logger, logging.WARNING, "empty_reply")
                return

            log_event(
                self._logger,
                logging.INFO,
                "llm_response",
                sender_id=message.sender_id,
                latency_ms=round(llm_result.latency_ms, 2),
            )

            chunks = chunk_text(reply, self._settings.max_reply_chars)

            destination_id: Optional[str | int]
            channel_index: Optional[int]
            if message.is_dm:
                if message.sender_id.startswith("!"):
                    destination_id = message.sender_id
                elif message.from_num is not None:
                    destination_id = message.from_num
                else:
                    destination_id = message.sender_id
                channel_index = None
            else:
                destination_id = None
                channel_index = message.channel or 0

            for idx, chunk in enumerate(chunks, start=1):
                send_start = time.perf_counter()
                if not self._client:
                    raise RuntimeError("Meshtastic client not available")
                self._client.send_text(chunk, destination_id, channel_index)
                send_latency = (time.perf_counter() - send_start) * 1000
                log_event(
                    self._logger,
                    logging.INFO,
                    "message_out",
                    sender_id=message.sender_id,
                    channel=channel_index,
                    is_dm=message.is_dm,
                    chunk_index=idx,
                    chunk_count=len(chunks),
                    send_latency_ms=round(send_latency, 2),
                )

            outbound_record = MessageRecord(
                direction="out",
                sender_id=message.sender_id,
                sender_short_name=message.sender_short_name,
                sender_long_name=message.sender_long_name,
                channel=message.channel,
                text=reply,
                timestamp=now_ts(),
                latency_ms=llm_result.latency_ms,
                message_id=None,
            )
            self._storage.add_message(outbound_record)
        except Exception as exc:  # pragma: no cover
            log_event(
                self._logger,
                logging.ERROR,
                "message_handler_error",
                error=str(exc),
            )

    def _should_respond(self, message: InboundMessage) -> bool:
        if self._settings.respond_to_dms_only and not message.is_dm:
            return False

        if self._settings.allowed_channels and not message.is_dm:
            if message.channel not in self._settings.allowed_channels:
                return False

        if self._settings.allowed_senders:
            candidates = {message.sender_id}
            if message.from_num is not None:
                candidates.add(str(message.from_num))
            if not any(candidate in self._settings.allowed_senders for candidate in candidates):
                return False

        prefix = self._settings.trigger_prefix
        if prefix and not message.text.startswith(prefix):
            return False

        return True


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level, settings.data_dir / "logs")
    logger = logging.getLogger("meshtastic_llm_bridge")

    log_event(
        logger,
        logging.INFO,
        "startup",
        ollama_host=settings.ollama_host,
        ollama_model=settings.ollama_model,
    )

    service = BridgeService(settings=settings, logger=logger)
    service.run_forever()
