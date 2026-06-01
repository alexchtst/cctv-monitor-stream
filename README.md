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

Run the paired AI engine in another terminal:

```bash
cd ../ai-engine
python -m venv .venv
. .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn ai_engine.main:app --app-dir app --reload --port 9000
```

## Camera region configuration

For DVR/NVR streams like the `test-cctv/test.ipynb` checks, define one region per SPPG in
`CAMERA_REGIONS_JSON`. The gateway builds RTSP URLs internally and only exposes safe backend MJPEG
URLs to the frontend.

```env
CAMERA_REGIONS_JSON=[{"name":"SPPG TIMOHO","ip":"182.8.226.125","username":"admin","password":"...","channels":"1-16","stream":"02"},{"name":"SPPG KOKAP","ip":"157.15.82.24","username":"admin","password":"...","channels":"1-8","stream":"02"},{"name":"SPPG UMBULHARJO","ip":"182.8.225.2","username":"admin","password":"...","channels":"1-8","stream":"02"},{"name":"SPPG SEDAYU","ip":"...","username":"admin","password":"...","channels":"1-8","stream":"02"}]
```

Use `stream:"02"` for the lighter sub-stream or `stream:"01"` for the main stream. Explicit
`CAMERA_STREAMS_JSON` entries still work and override generated region cameras with the same `id`.

## Important Hik-Connect note

The `hikconnect` Python package is used for cloud login and camera/device discovery. Its public
API exposes `login`, `get_devices`, `get_cameras`, call status, unlock, and refresh-login behavior,
but it does not expose a direct video-frame API. For frame capture, set `CAMERA_STREAMS_JSON` with
the RTSP/HTTP stream URL for each camera/channel after the Hik-Connect credentials and camera access
are ready.

If `HIKCONNECT_USERNAME` and `HIKCONNECT_PASSWORD` are set, discovery failures are logged as warnings
and the service continues with `CAMERA_STREAMS_JSON`.

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
