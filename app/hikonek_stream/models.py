from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    streamUrl: str = ""
    activeDetections: list[ViolationType] = Field(default_factory=list)
    confidence: int = 0


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

