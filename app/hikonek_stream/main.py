from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .frame_pipeline import FramePipeline
from .settings import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="hikonek-stream", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
pipeline = FramePipeline(settings)


@app.on_event("startup")
async def startup() -> None:
    await pipeline.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await pipeline.stop()


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "ok": True,
        "cameras": len(pipeline.cameras),
        "activeLoops": len(pipeline.tasks),
        "aiEngineUrl": settings.ai_engine_url,
        "emailEnabled": pipeline.emailer.enabled,
    }


@app.post("/refresh-cameras")
async def refresh_cameras() -> dict[str, object]:
    await pipeline.refresh_cameras()
    return {"cameras": list(pipeline.cameras.values())}


@app.get("/cameras")
async def cameras() -> list[object]:
    return list(pipeline.cameras.values())


@app.get("/events")
async def events() -> list[object]:
    return list(pipeline.events)


@app.get("/stream/{camera_id}.mjpg")
async def stream(camera_id: str) -> StreamingResponse:
    if camera_id not in pipeline.cameras:
        raise HTTPException(status_code=404, detail="Camera not found")

    async def frames():
        while True:
            frame = pipeline.latest_frames.get(camera_id)
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(0.2)

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/ws/predictions")
async def prediction_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = pipeline.subscribe()
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        pipeline.unsubscribe(queue)
