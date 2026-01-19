"""Configuration handling for the bridge."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_csv(value: Optional[object]) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return [str(value).strip()]


class Settings(BaseSettings):
    """Application settings loaded from env and defaults."""

    serial_port: Optional[str] = Field(default=None, alias="SERIAL_PORT")
    baudrate: int = Field(default=115200, alias="BAUDRATE")

    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")
    ollama_model: str = Field(default="mistral", alias="OLLAMA_MODEL")

    trigger_prefix: str = Field(default="!ai ", alias="TRIGGER_PREFIX")
    respond_to_dms_only: bool = Field(default=False, alias="RESPOND_TO_DMS_ONLY")
    allowed_channels: List[int] = Field(default_factory=list, alias="ALLOWED_CHANNELS")
    allowed_senders: List[str] = Field(default_factory=list, alias="ALLOWED_SENDERS")

    max_reply_chars: int = Field(default=200, alias="MAX_REPLY_CHARS")
    memory_turns: int = Field(default=6, alias="MEMORY_TURNS")

    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
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

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return value.upper().strip()


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings()
