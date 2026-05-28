# hikonek-stream

Stream gateway for the employee-monitor CCTV flow:

1. Authenticate to Hik-Connect and discover devices/cameras.
2. Read CCTV frames from configured stream URLs.
3. Send frames to the YOLO AI engine.
4. Store annotated frames and normalized violation events for FE.
5. Send email notifications for detected violations.

The FE violation contract is:

```text
"NO HELMET" | "NO MASK" | "SMOKING" | "RESTRICTED AREA"
```

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn hikonek_stream.main:app --app-dir app --reload --port 8010
```

## Important Hik-Connect note

The `hikconnect` Python package is used for cloud login and camera/device discovery. Its public
API exposes `login`, `get_devices`, `get_cameras`, call status, unlock, and refresh-login behavior,
but it does not expose a direct video-frame API. For frame capture, set `CAMERA_STREAMS_JSON` with
the RTSP/HTTP stream URL for each camera/channel after the Hik-Connect credentials and camera access
are ready.

## API

- `GET /health` - service state.
- `GET /cameras` - cameras discovered/configured for FE.
- `GET /events` - recent prediction events for FE.
- `GET /stream/{camera_id}.mjpg` - latest annotated frame as MJPEG.
- `WS /ws/predictions` - live prediction events.

## Expected YOLO response

The gateway accepts several common response shapes, but this shape is preferred:

```json
{
  "predictions": [
    {
      "type": "NO HELMET",
      "confidence": 0.96,
      "bbox": [100, 80, 220, 260],
      "analysis": "Worker detected without helmet"
    }
  ],
  "annotated_frame": "<optional base64 JPEG>"
}
```

If `annotated_frame` is omitted, this service draws simple boxes and labels from `bbox`.

