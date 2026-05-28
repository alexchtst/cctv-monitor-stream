from __future__ import annotations

import base64
from typing import Any

import httpx

from .models import AiEngineResult, Detection, VALID_VIOLATIONS
from .settings import Settings


class AiEngineClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def predict(self, frame_jpeg: bytes, camera_id: str) -> AiEngineResult:
        async with httpx.AsyncClient(timeout=self.settings.ai_engine_timeout_seconds) as client:
            response = await client.post(
                self.settings.ai_engine_url,
                data={"camera_id": camera_id},
                files={"frame": ("frame.jpg", frame_jpeg, "image/jpeg")},
            )
            response.raise_for_status()
            return self._parse_response(response.json())

    def _parse_response(self, payload: dict[str, Any]) -> AiEngineResult:
        raw_predictions = (
            payload.get("predictions")
            or payload.get("detections")
            or payload.get("result")
            or []
        )
        detections: list[Detection] = []

        for item in raw_predictions:
            if not isinstance(item, dict):
                continue
            raw_type = str(item.get("type") or item.get("label") or item.get("class") or "").upper()
            if raw_type not in VALID_VIOLATIONS:
                continue

            confidence = float(item.get("confidence") or item.get("score") or 0)
            if confidence > 1:
                confidence = confidence / 100
            detections.append(
                Detection(
                    type=raw_type,  # type: ignore[arg-type]
                    confidence=confidence,
                    bbox=item.get("bbox") or item.get("box"),
                    analysis=item.get("analysis"),
                )
            )

        annotated_frame = None
        encoded = payload.get("annotated_frame") or payload.get("frame")
        if isinstance(encoded, str) and encoded:
            if "," in encoded:
                encoded = encoded.split(",", 1)[1]
            annotated_frame = base64.b64decode(encoded)

        return AiEngineResult(detections=detections, annotated_frame=annotated_frame)
