from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ViolationType = Literal["NO HELMET", "NO MASK", "SMOKING", "RESTRICTED AREA"]
Severity = Literal["high", "medium", "low"]
NotificationStatus = Literal["queued", "sent", "muted"]
CameraStatus = Literal["online", "degraded", "offline"]

VALID_VIOLATIONS: set[str] = {"NO HELMET", "NO MASK", "SMOKING", "RESTRICTED AREA"}


class CameraStream(BaseModel):
    id: str
    name: str
    location: str = ""
    hikonekChannelId: str
    status: CameraStatus = "offline"
    streamUrl: str = Field(default="", exclude=True)
    activeDetections: list[ViolationType] = Field(default_factory=list)
    confidence: int = 0


class CameraRegion(BaseModel):
    name: str
    ip: str
    username: str
    password: str
    channels: list[int]
    stream: str = "02"
    port: int = 554

    @field_validator("channels", mode="before")
    @classmethod
    def parse_channels(cls, value: object) -> list[int]:
        if isinstance(value, str):
            channels: list[int] = []
            for part in value.split(","):
                item = part.strip()
                if not item:
                    continue
                if "-" in item:
                    start, end = [int(bound.strip()) for bound in item.split("-", 1)]
                    channels.extend(range(start, end + 1))
                else:
                    channels.append(int(item))
            return channels
        return value  # type: ignore[return-value]

    @field_validator("stream")
    @classmethod
    def validate_stream(cls, value: str) -> str:
        return value.zfill(2)


class Detection(BaseModel):
    type: ViolationType
    confidence: float
    bbox: list[float] | None = None
    analysis: str | None = None


class PredictionEvent(BaseModel):
    id: str
    time: str
    timestamp: datetime
    cameraId: str
    camera: str
    type: ViolationType
    confidence: int
    severity: Severity
    notification: NotificationStatus
    analysis: str | None = None


class AiEngineResult(BaseModel):
    detections: list[Detection] = Field(default_factory=list)
    annotated_frame: bytes | None = None
