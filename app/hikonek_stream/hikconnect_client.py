from __future__ import annotations

import logging

from hikconnect.exceptions import LoginError
from hikconnect.api import HikConnect

from .models import CameraStream
from .settings import Settings

logger = logging.getLogger(__name__)


class HikConnectDiscovery:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def discover(self) -> list[CameraStream]:
        if not self.settings.hikconnect_username or not self.settings.hikconnect_password:
            logger.info("Hik-Connect credentials are empty; skipping cloud discovery")
            return []

        discovered: list[CameraStream] = []
        try:
            async with HikConnect() as api:
                await api.login(
                    self.settings.hikconnect_username,
                    self.settings.hikconnect_password,
                )
                devices = [device async for device in api.get_devices()]

                for device in devices:
                    serial = str(device.get("serial", ""))
                    device_name = str(device.get("name") or serial or "Hikvision device")
                    if not serial:
                        continue

                    cameras = [camera async for camera in api.get_cameras(serial)]
                    for camera in cameras:
                        channel = str(camera.get("channel_number") or camera.get("id") or "")
                        camera_name = str(camera.get("name") or f"{device_name} channel {channel}")
                        signal_status = int(camera.get("signal_status") or 0)
                        discovered.append(
                            CameraStream(
                                id=f"{serial}-{channel}",
                                name=camera_name,
                                location=device_name,
                                hikonekChannelId=f"{serial}:{channel}",
                                status="online" if signal_status == 1 else "offline",
                            )
                        )

                if api.is_refresh_login_needed():
                    await api.refresh_login()
        except LoginError:
            logger.warning("Hik-Connect login failed; continuing with configured camera streams")
        except Exception as exc:
            logger.warning(
                "Hik-Connect discovery failed; continuing with configured camera streams: %s",
                exc,
            )

        return discovered
