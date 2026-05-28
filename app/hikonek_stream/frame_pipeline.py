from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from datetime import datetime

import cv2
import numpy as np

from .ai_engine import AiEngineClient
from .emailer import EmailNotifier
from .hikconnect_client import HikConnectDiscovery
from .models import CameraStream, Detection, PredictionEvent, ViolationType
from .settings import Settings

logger = logging.getLogger(__name__)


class FramePipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ai_engine = AiEngineClient(settings)
        self.emailer = EmailNotifier(settings)
        self.discovery = HikConnectDiscovery(settings)
        self.cameras: dict[str, CameraStream] = {}
        self.events: deque[PredictionEvent] = deque(maxlen=settings.max_events)
        self.latest_frames: dict[str, bytes] = {}
        self.subscribers: set[asyncio.Queue[PredictionEvent]] = set()
        self.tasks: list[asyncio.Task[None]] = []
        self._last_event_at: dict[tuple[str, str], float] = {}
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await self.refresh_cameras()
        for camera in self.cameras.values():
            if camera.streamUrl:
                self.tasks.append(asyncio.create_task(self._camera_loop(camera)))

    async def stop(self) -> None:
        self._running = False
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

    async def refresh_cameras(self) -> None:
        configured = {camera.id: camera for camera in self.settings.configured_cameras()}
        discovered = {camera.id: camera for camera in await self.discovery.discover()}

        for camera_id, camera in discovered.items():
            if camera_id in configured:
                configured[camera_id] = configured[camera_id].model_copy(
                    update={
                        "name": configured[camera_id].name or camera.name,
                        "location": configured[camera_id].location or camera.location,
                        "hikonekChannelId": configured[camera_id].hikonekChannelId
                        or camera.hikonekChannelId,
                        "status": camera.status,
                    }
                )
            else:
                configured[camera_id] = camera

        self.cameras = configured

    def subscribe(self) -> asyncio.Queue[PredictionEvent]:
        queue: asyncio.Queue[PredictionEvent] = asyncio.Queue(maxsize=100)
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[PredictionEvent]) -> None:
        self.subscribers.discard(queue)

    async def _camera_loop(self, camera: CameraStream) -> None:
        while self._running:
            try:
                frame = await asyncio.to_thread(self._read_frame, camera.streamUrl)
                if frame is None:
                    camera.status = "degraded"
                    await asyncio.sleep(self.settings.frame_interval_seconds)
                    continue

                camera.status = "online"
                frame_jpeg = self._encode_jpeg(frame)
                result = await self.ai_engine.predict(frame_jpeg, camera.id)
                annotated = result.annotated_frame or self._annotate(frame, result.detections)
                self.latest_frames[camera.id] = annotated
                await self._handle_detections(camera, result.detections)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Camera loop failed for %s", camera.id)
                camera.status = "degraded"

            await asyncio.sleep(self.settings.frame_interval_seconds)

    def _read_frame(self, stream_url: str) -> np.ndarray | None:
        capture = cv2.VideoCapture(stream_url)
        try:
            ok, frame = capture.read()
            return frame if ok else None
        finally:
            capture.release()

    def _encode_jpeg(self, frame: np.ndarray) -> bytes:
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("Failed to encode frame as JPEG")
        return encoded.tobytes()

    def _annotate(self, frame: np.ndarray, detections: list[Detection]) -> bytes:
        output = frame.copy()
        for detection in detections:
            label = f"{detection.type} {int(detection.confidence * 100)}%"
            if detection.bbox and len(detection.bbox) >= 4:
                x1, y1, x2, y2 = [int(value) for value in detection.bbox[:4]]
                cv2.rectangle(output, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(
                    output,
                    label,
                    (x1, max(y1 - 8, 16)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2,
                )
        return self._encode_jpeg(output)

    async def _handle_detections(self, camera: CameraStream, detections: list[Detection]) -> None:
        active: list[ViolationType] = []
        top_confidence = 0

        for detection in detections:
            if detection.confidence < self.settings.event_min_confidence:
                continue

            confidence = int(round(detection.confidence * 100))
            active.append(detection.type)
            top_confidence = max(top_confidence, confidence)

            key = (camera.id, detection.type)
            now = time.time()
            if now - self._last_event_at.get(key, 0) < self.settings.event_dedupe_seconds:
                continue
            self._last_event_at[key] = now

            event = PredictionEvent(
                id=f"evt-{uuid.uuid4().hex[:10]}",
                time=datetime.now().strftime("%I:%M %p"),
                timestamp=datetime.now(),
                cameraId=camera.id,
                camera=camera.name,
                type=detection.type,
                confidence=confidence,
                severity=self._severity(detection.type, confidence),
                notification="queued",
                analysis=detection.analysis,
            )
            sent = await self.emailer.send(event)
            event.notification = "sent" if sent else "queued"
            self.events.appendleft(event)
            await self._publish(event)

        camera.activeDetections = active
        camera.confidence = top_confidence

    def _severity(self, violation: str, confidence: int) -> str:
        if violation in {"NO HELMET", "NO MASK"} or confidence >= 90:
            return "high"
        if violation in {"SMOKING", "RESTRICTED AREA"}:
            return "medium"
        return "low"

    async def _publish(self, event: PredictionEvent) -> None:
        stale: list[asyncio.Queue[PredictionEvent]] = []
        for queue in self.subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self.unsubscribe(queue)

