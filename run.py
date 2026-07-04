import os
from pathlib import Path

import uvicorn
from uvicorn.config import LOGGING_CONFIG

if __name__ == "__main__":
    logs_root = Path(__file__).resolve().parent / "app" / "logs"
    logs_root.mkdir(parents=True, exist_ok=True)

    # 修改默认日志配置
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = (
        '%(asctime)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s'
    )
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["handlers"]["default_file"] = {
        "class": "logging.handlers.TimedRotatingFileHandler",
        "formatter": "default",
        "filename": str(logs_root / "uvicorn.log"),
        "when": "midnight",
        "interval": 1,
        "backupCount": 30,
        "encoding": "utf-8",
    }
    LOGGING_CONFIG["handlers"]["access_file"] = {
        "class": "logging.handlers.TimedRotatingFileHandler",
        "formatter": "access",
        "filename": str(logs_root / "access.log"),
        "when": "midnight",
        "interval": 1,
        "backupCount": 30,
        "encoding": "utf-8",
    }
    LOGGING_CONFIG["loggers"]["uvicorn"]["handlers"] = ["default", "default_file"]
    LOGGING_CONFIG["loggers"]["uvicorn.error"]["handlers"] = ["default", "default_file"]
    LOGGING_CONFIG["loggers"]["uvicorn.access"]["handlers"] = ["access", "access_file"]

    reload_flag = os.getenv("UVICORN_RELOAD", "0").lower() in {"1", "true", "yes", "on"}
    trust_proxy_headers = os.getenv("TRUST_PROXY_HEADERS", "0").lower() in {"1", "true", "yes", "on"}
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=9999,
        reload=reload_flag,
        log_config=LOGGING_CONFIG,
        proxy_headers=trust_proxy_headers,
        forwarded_allow_ips="*" if trust_proxy_headers else None,
    )
