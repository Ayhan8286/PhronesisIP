import logging
import json
import sys
import uuid
from typing import Any, Dict, Optional
from datetime import datetime

# Context vars could be used here via contextvars in a full async setup
# For simplicity, we provide a structured logger wrapper

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "filename": record.filename,
            "line": record.lineno
        }
        
        # Extract contextual attributes if passed via `extra={...}`
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        if hasattr(record, "firm_id"):
            log_obj["firm_id"] = record.firm_id
        if hasattr(record, "user_id"):
            log_obj["user_id"] = record.user_id
            
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)

def get_base_logger(name: str = "patent_iq") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

class StructuredLogger:
    """Wrapper that ensures request context is attached to all logs."""
    def __init__(self, name: str, request_id: Optional[str] = None, firm_id: Optional[str] = None, user_id: Optional[str] = None):
        self.logger = get_base_logger(name)
        self.extra = {
            "request_id": request_id or str(uuid.uuid4()),
            "firm_id": firm_id,
            "user_id": user_id
        }

    def info(self, msg: str, **kwargs):
        self.logger.info(msg, extra=self.extra, **kwargs)

    def error(self, msg: str, exc_info: bool = False, **kwargs):
        self.logger.error(msg, extra=self.extra, exc_info=exc_info, **kwargs)

    def warning(self, msg: str, **kwargs):
        self.logger.warning(msg, extra=self.extra, **kwargs)
        
    def debug(self, msg: str, **kwargs):
        self.logger.debug(msg, extra=self.extra, **kwargs)
