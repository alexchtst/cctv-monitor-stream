from __future__ import annotations

import json
import logging

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import CameraStream

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    hikconnect_username: str = ""
    hikconnect_password: str = ""

    camera_streams_json: str = "[]"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    ai_engine_url: str = "http://localhost:9000/predict"
    ai_engine_timeout_seconds: float = 10.0

    frame_interval_seconds: float = 1.0
    event_min_confidence: float = 0.65
    event_dedupe_seconds: int = 60
    max_events: int = 200

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "alerts@example.com"
    smtp_to: str = ""
    smtp_tls: bool = True

    @field_validator("frame_interval_seconds")
    @classmethod
    def validate_frame_interval(cls, value: float) -> float:
        return max(value, 0.1)

    def configured_cameras(self) -> list[CameraStream]:
        if not self.camera_streams_json.strip():
            return []
        try:
            raw = json.loads(self.camera_streams_json)
        except json.JSONDecodeError:
            logger.exception("CAMERA_STREAMS_JSON is not valid JSON")
            return []
        return [CameraStream.model_validate(item) for item in raw]

    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
