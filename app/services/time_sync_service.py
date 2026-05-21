import socket
import struct
import subprocess
from datetime import datetime, timezone

from fastapi import HTTPException

from app.log import logger


class TimeSyncService:
    NTP_DELTA_SECONDS = 2_208_988_800

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _query_ntp_time(self, server: str, timeout: float = 5.0) -> datetime:
        host = str(server or "").strip()
        if not host:
            raise HTTPException(status_code=400, detail="时间服务器不能为空")

        packet = b"\x1b" + 47 * b"\0"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(timeout)
                sock.sendto(packet, (host, 123))
                data, _ = sock.recvfrom(48)
        except OSError as exc:
            logger.warning("[time_sync.ntp] query_failed server={} error={}", host, repr(exc))
            raise HTTPException(status_code=400, detail=f"时间服务器连接失败：{host}")

        if len(data) < 48:
            raise HTTPException(status_code=400, detail="时间服务器返回数据不完整")

        seconds, fraction = struct.unpack("!II", data[40:48])
        timestamp = seconds - self.NTP_DELTA_SECONDS + fraction / 2**32
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    def _run_set_time(self, ntp_time: datetime) -> subprocess.CompletedProcess:
        target = ntp_time.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return subprocess.run(
            ["date", "-u", "-s", target],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    def _format_dt(self, value: datetime, tz_name: str | None = None) -> str:
        # The configured timezone is persisted for deployment tools; Python stdlib
        # cannot guarantee every IANA zone is available on all target images.
        return value.astimezone().isoformat(timespec="seconds")

    def status(self, config: dict) -> dict:
        server = str(config.get("time_sync_server") or "ntp.aliyun.com").strip()
        max_offset = int(config.get("time_sync_max_offset_seconds") or 5)
        timezone_name = str(config.get("time_sync_timezone") or "Asia/Shanghai").strip()

        ntp_time = self._query_ntp_time(server)
        local_time = self._utc_now()
        offset_seconds = round((ntp_time - local_time).total_seconds(), 3)
        return {
            "enabled": bool(config.get("time_sync_enabled", True)),
            "server": server,
            "timezone": timezone_name,
            "local_time": self._format_dt(local_time, timezone_name),
            "ntp_time": self._format_dt(ntp_time, timezone_name),
            "offset_seconds": offset_seconds,
            "max_offset_seconds": max_offset,
            "within_tolerance": abs(offset_seconds) <= max_offset,
        }

    def sync(self, config: dict) -> dict:
        if not bool(config.get("time_sync_enabled", True)):
            raise HTTPException(status_code=400, detail="时间同步未启用")

        server = str(config.get("time_sync_server") or "ntp.aliyun.com").strip()
        ntp_time = self._query_ntp_time(server)
        logger.info("[time_sync.sync] start server={} target={}", server, ntp_time.isoformat())

        try:
            completed = self._run_set_time(ntp_time)
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("[time_sync.sync] command_failed server={} error={}", server, repr(exc))
            raise HTTPException(status_code=400, detail="执行系统校时失败，请确认容器安装 date 并具备 CAP_SYS_TIME 权限")

        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout or "").strip()
            logger.warning(
                "[time_sync.sync] rejected server={} returncode={} stderr={}",
                server,
                completed.returncode,
                stderr,
            )
            raise HTTPException(
                status_code=400,
                detail="系统拒绝校时，请给容器增加 CAP_SYS_TIME/特权模式，或在宿主机配置 NTP 同步",
            )

        result = self.status(config)
        result["synced"] = True
        return result


time_sync_service = TimeSyncService()
