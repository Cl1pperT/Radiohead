"""Configuration handling for the bridge."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import DotEnvSettingsSource, EnvSettingsSource


def _parse_csv(value: Optional[object]) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                data = json.loads(stripped)
                if isinstance(data, list):
                    return [str(item).strip() for item in data if str(item).strip()]
            except json.JSONDecodeError:
                pass
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return [str(value).strip()]


class Settings(BaseSettings):
    """Application settings loaded from env and defaults."""

    meshtastic_connection: str = Field(
        default="serial", alias="MESHTASTIC_CONNECTION"
    )
    serial_port: Optional[str] = Field(default=None, alias="SERIAL_PORT")
    baudrate: int = Field(default=115200, alias="BAUDRATE")
    meshtastic_host: str = Field(default="localhost", alias="MESHTASTIC_HOST")
    meshtastic_port: int = Field(default=4403, alias="MESHTASTIC_PORT")

    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")
    ollama_model: str = Field(default="mistral", alias="OLLAMA_MODEL")

    trigger_prefix: str = Field(default="!ai ", alias="TRIGGER_PREFIX")
    respond_to_dms_only: bool = Field(default=False, alias="RESPOND_TO_DMS_ONLY")
    allowed_channels: List[int] = Field(default_factory=list, alias="ALLOWED_CHANNELS")
    allowed_senders: List[str] = Field(default_factory=list, alias="ALLOWED_SENDERS")

    max_reply_chars: int = Field(default=200, alias="MAX_REPLY_CHARS")
    memory_turns: int = Field(default=6, alias="MEMORY_TURNS")
    duplicate_prompt_window_s: float = Field(
        default=60.0, alias="DUPLICATE_PROMPT_WINDOW_S"
    )

    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            CsvEnvSettingsSource(settings_cls),
            CsvDotEnvSettingsSource(settings_cls),
            file_secret_settings,
        )

    @field_validator("allowed_channels", mode="before")
    @classmethod
    def _parse_channels(cls, value: Optional[object]) -> List[int]:
        items = _parse_csv(value)
        channels: List[int] = []
        for item in items:
            try:
                channels.append(int(item))
            except ValueError as exc:
                raise ValueError(f"Invalid channel value: {item}") from exc
        return channels

    @field_validator("allowed_senders", mode="before")
    @classmethod
    def _parse_senders(cls, value: Optional[object]) -> List[str]:
        return _parse_csv(value)

    @field_validator("max_reply_chars")
    @classmethod
    def _validate_max_reply_chars(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_REPLY_CHARS must be > 0")
        return value

    @field_validator("memory_turns")
    @classmethod
    def _validate_memory_turns(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MEMORY_TURNS must be > 0")
        return value

    @field_validator("duplicate_prompt_window_s")
    @classmethod
    def _validate_duplicate_prompt_window(cls, value: float) -> float:
        if value < 0:
            raise ValueError("DUPLICATE_PROMPT_WINDOW_S must be >= 0")
        return value

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return value.upper().strip()

    @field_validator("meshtastic_connection")
    @classmethod
    def _validate_connection(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"serial", "tcp"}:
            raise ValueError("MESHTASTIC_CONNECTION must be 'serial' or 'tcp'")
        return normalized

    @field_validator("meshtastic_port")
    @classmethod
    def _validate_port(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MESHTASTIC_PORT must be > 0")
        return value


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings()


class CsvEnvSettingsSource(EnvSettingsSource):
    _csv_fields = {"allowed_channels", "allowed_senders"}

    def decode_complex_value(self, field_name, field, value):  # type: ignore[override]
        if field_name in self._csv_fields:
            return value
        return super().decode_complex_value(field_name, field, value)


class CsvDotEnvSettingsSource(DotEnvSettingsSource):
    _csv_fields = {"allowed_channels", "allowed_senders"}

    def decode_complex_value(self, field_name, field, value):  # type: ignore[override]
        if field_name in self._csv_fields:
            return value
        return super().decode_complex_value(field_name, field, value)
