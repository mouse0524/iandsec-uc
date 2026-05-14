import sys
from pathlib import Path

from loguru import logger as loguru_logger

from app.settings import settings


class Loggin:
    def __init__(self) -> None:
        self.debug = settings.DEBUG
        if self.debug:
            self.level = "DEBUG"
        else:
            self.level = "INFO"

    def setup_logger(self):
        log_dir = Path(settings.LOGS_ROOT)
        log_dir.mkdir(parents=True, exist_ok=True)

        loguru_logger.remove()
        log_format = (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
            "{name}:{function}:{line} - {message}"
        )
        loguru_logger.add(sink=sys.stdout, level=self.level, format=log_format)
        loguru_logger.add(
            sink=log_dir / "app_{time:YYYY-MM-DD}.log",
            level=self.level,
            format=log_format,
            rotation="00:00",
            retention="30 days",
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=self.debug,
        )
        return loguru_logger


loggin = Loggin()
logger = loggin.setup_logger()
