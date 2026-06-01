from __future__ import annotations

import json
import logging

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import CameraRegion, CameraStream

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    hikconnect_username: str = ""
    hikconnect_password: str = ""

    camera_streams_json: str = "[]"
    camera_regions_json: str = "[]"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    ai_engine_url: str = "http://localhost:9000/predict"
    ai_engine_timeout_seconds: float = 10.0

    frame_interval_seconds: float = 1.0
    rtsp_timeout_microseconds: int = 3_000_000
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
        cameras = self._configured_region_cameras()
        if not self.camera_streams_json.strip():
            return cameras
        try:
            raw = json.loads(self.camera_streams_json)
        except json.JSONDecodeError:
            logger.exception("CAMERA_STREAMS_JSON is not valid JSON")
            return cameras
        explicit_cameras = [CameraStream.model_validate(item) for item in raw]
        explicit_by_id = {camera.id: camera for camera in explicit_cameras}
        region_by_id = {camera.id: camera for camera in cameras}
        region_by_id.update(explicit_by_id)
        return list(region_by_id.values())

    def configured_regions(self) -> list[CameraRegion]:
        if not self.camera_regions_json.strip():
            return []
        try:
            raw = json.loads(self.camera_regions_json)
        except json.JSONDecodeError:
            logger.exception("CAMERA_REGIONS_JSON is not valid JSON")
            return []
        return [CameraRegion.model_validate(item) for item in raw]

    def _configured_region_cameras(self) -> list[CameraStream]:
        cameras: list[CameraStream] = []
        for region in self.configured_regions():
            location = region.name.strip()
            region_id = self._slug(location)
            for channel in region.channels:
                cameras.append(
                    CameraStream(
                        id=f"{region_id}-cam{channel:02d}",
                        name=f"Camera {channel:02d}",
                        location=location,
                        hikonekChannelId=f"{region.ip}:{channel:02d}{region.stream}",
                        streamUrl=(
                            f"rtsp://{region.username}:{region.password}@{region.ip}:{region.port}"
                            f"/Streaming/Channels/{channel}{region.stream}"
                        ),
                    )
                )
        return cameras

    def _slug(self, value: str) -> str:
        slug = "".join(char.lower() if char.isalnum() else "-" for char in value)
        return "-".join(part for part in slug.split("-") if part)

    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
