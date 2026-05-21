import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.services.time_sync_service import TimeSyncService


class TimeSyncServiceTestCase(unittest.TestCase):
    def test_status_reports_offset_from_ntp_server(self):
        service = TimeSyncService()
        ntp_time = datetime(2026, 5, 21, 8, 0, 5, tzinfo=timezone.utc)
        local_time = datetime(2026, 5, 21, 8, 0, 0, tzinfo=timezone.utc)

        with patch.object(service, "_query_ntp_time", return_value=ntp_time), patch.object(
            service, "_utc_now", return_value=local_time
        ):
            result = service.status(
                {
                    "time_sync_enabled": True,
                    "time_sync_server": "ntp.aliyun.com",
                    "time_sync_max_offset_seconds": 3,
                    "time_sync_timezone": "Asia/Shanghai",
                }
            )

        self.assertTrue(result["enabled"])
        self.assertEqual(result["server"], "ntp.aliyun.com")
        self.assertEqual(result["offset_seconds"], 5.0)
        self.assertFalse(result["within_tolerance"])

    def test_sync_rejects_disabled_configuration(self):
        service = TimeSyncService()

        with self.assertRaises(HTTPException) as ctx:
            service.sync({"time_sync_enabled": False, "time_sync_server": "ntp.aliyun.com"})

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("未启用", ctx.exception.detail)

    def test_sync_uses_ntp_timestamp_without_shell_interpolation(self):
        service = TimeSyncService()
        ntp_time = datetime(2026, 5, 21, 8, 0, 5, tzinfo=timezone.utc)
        completed = MagicMock(returncode=0, stdout="", stderr="")

        with patch.object(service, "_query_ntp_time", return_value=ntp_time), patch.object(
            service, "_run_set_time", return_value=completed
        ) as run_set_time:
            result = service.sync(
                {
                    "time_sync_enabled": True,
                    "time_sync_server": "ntp.aliyun.com",
                    "time_sync_max_offset_seconds": 3,
                    "time_sync_timezone": "Asia/Shanghai",
                }
            )

        self.assertTrue(result["synced"])
        run_set_time.assert_called_once_with(ntp_time)

    def test_query_ntp_time_uses_udp_packet(self):
        service = TimeSyncService()
        packet = bytearray(48)
        packet[40:44] = (service.NTP_DELTA_SECONDS + 1).to_bytes(4, "big")
        fake_socket = MagicMock()
        fake_socket.recvfrom.return_value = (bytes(packet), ("ntp.aliyun.com", 123))
        fake_socket.__enter__.return_value = fake_socket

        with patch("app.services.time_sync_service.socket.socket", return_value=fake_socket) as socket_factory:
            result = service._query_ntp_time("ntp.aliyun.com")

        socket_factory.assert_called_once()
        fake_socket.sendto.assert_called_once()
        self.assertEqual(result, datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
