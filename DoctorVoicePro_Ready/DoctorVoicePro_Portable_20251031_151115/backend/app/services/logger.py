"""
Comprehensive Logging & Monitoring Service
모든 시스템 이벤트, 성능 메트릭, 에러 추적
"""

import logging
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
import traceback


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventType(str, Enum):
    # Network & API
    API_REQUEST_START = "api_request_start"
    API_REQUEST_END = "api_request_end"
    API_ERROR = "api_error"
    NETWORK_TIMEOUT = "network_timeout"

    # Authentication
    LOGIN_ATTEMPT = "login_attempt"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    TOKEN_EXPIRED = "token_expired"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

    # Database
    DB_CONNECTION = "db_connection"
    DB_QUERY_START = "db_query_start"
    DB_QUERY_END = "db_query_end"
    DB_ERROR = "db_error"
    DB_TIMEOUT = "db_timeout"

    # File System
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_ERROR = "file_error"
    DISK_SPACE_WARNING = "disk_space_warning"

    # Application
    APP_STARTUP = "app_startup"
    APP_SHUTDOWN = "app_shutdown"
    CONFIG_LOADED = "config_loaded"
    HEALTH_CHECK = "health_check"

    # User Actions
    USER_ACTION = "user_action"
    PAGE_VIEW = "page_view"
    FORM_SUBMIT = "form_submit"
    FILE_UPLOAD = "file_upload"

    # Performance
    SLOW_QUERY = "slow_query"
    HIGH_MEMORY = "high_memory"
    HIGH_CPU = "high_cpu"

    # External Services
    EXTERNAL_API_CALL = "external_api_call"
    EXTERNAL_SERVICE_ERROR = "external_service_error"


class AppLogger:
    def __init__(self):
        self.logger = logging.getLogger("doctor_voice_pro")
        self.logger.setLevel(logging.DEBUG)

        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)

        # File Handler
        file_handler = logging.FileHandler("app.log")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)

        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

        # Metrics storage (in-memory, should use Redis in production)
        self.metrics: Dict[str, Any] = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_error": 0,
            "response_times": [],
            "db_queries": 0,
            "errors": [],
        }

    def log_event(
        self,
        event_type: EventType,
        level: LogLevel = LogLevel.INFO,
        message: str = "",
        data: Optional[Dict] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """통합 이벤트 로깅"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "level": level.value,
            "message": message,
            "user_id": user_id,
            "request_id": request_id,
            "data": data or {},
        }

        log_message = json.dumps(log_data)

        if level == LogLevel.DEBUG:
            self.logger.debug(log_message)
        elif level == LogLevel.INFO:
            self.logger.info(log_message)
        elif level == LogLevel.WARNING:
            self.logger.warning(log_message)
        elif level == LogLevel.ERROR:
            self.logger.error(log_message)
            self.metrics["errors"].append(log_data)
        elif level == LogLevel.CRITICAL:
            self.logger.critical(log_message)

    # Network & API
    def log_api_request(self, method: str, endpoint: str, request_id: str, user_id: Optional[str] = None):
        self.metrics["requests_total"] += 1
        self.log_event(
            EventType.API_REQUEST_START,
            message=f"{method} {endpoint}",
            data={"method": method, "endpoint": endpoint},
            user_id=user_id,
            request_id=request_id,
        )

    def log_api_response(self, request_id: str, status_code: int, response_time: float):
        if status_code < 400:
            self.metrics["requests_success"] += 1
        else:
            self.metrics["requests_error"] += 1

        self.metrics["response_times"].append(response_time)
        if len(self.metrics["response_times"]) > 1000:
            self.metrics["response_times"] = self.metrics["response_times"][-1000:]

        level = LogLevel.INFO if status_code < 400 else LogLevel.ERROR
        self.log_event(
            EventType.API_REQUEST_END,
            level=level,
            message=f"Response: {status_code} in {response_time:.3f}s",
            data={"status_code": status_code, "response_time": response_time},
            request_id=request_id,
        )

    # Authentication
    def log_login_attempt(self, email: str, ip_address: str):
        self.log_event(
            EventType.LOGIN_ATTEMPT,
            message=f"Login attempt for {email}",
            data={"email": email, "ip_address": ip_address},
        )

    def log_login_success(self, user_id: str, email: str):
        self.log_event(
            EventType.LOGIN_SUCCESS,
            message=f"Login successful for {email}",
            user_id=user_id,
            data={"email": email},
        )

    def log_login_failure(self, email: str, reason: str):
        self.log_event(
            EventType.LOGIN_FAILURE,
            level=LogLevel.WARNING,
            message=f"Login failed for {email}: {reason}",
            data={"email": email, "reason": reason},
        )

    # Database
    def log_db_query(self, query: str, duration: float):
        self.metrics["db_queries"] += 1
        level = LogLevel.WARNING if duration > 1.0 else LogLevel.DEBUG
        event_type = EventType.SLOW_QUERY if duration > 1.0 else EventType.DB_QUERY_END

        self.log_event(
            event_type,
            level=level,
            message=f"Query executed in {duration:.3f}s",
            data={"query": query[:200], "duration": duration},
        )

    # Errors
    def log_error(self, error: Exception, context: Optional[Dict] = None, user_id: Optional[str] = None):
        self.log_event(
            EventType.API_ERROR,
            level=LogLevel.ERROR,
            message=str(error),
            data={
                "error_type": type(error).__name__,
                "traceback": traceback.format_exc(),
                "context": context or {},
            },
            user_id=user_id,
        )

    # Performance
    def log_performance_metric(self, metric_name: str, value: float, threshold: Optional[float] = None):
        level = LogLevel.WARNING if threshold and value > threshold else LogLevel.INFO
        self.log_event(
            EventType.HIGH_MEMORY if "memory" in metric_name else EventType.HIGH_CPU,
            level=level,
            message=f"{metric_name}: {value}",
            data={"metric": metric_name, "value": value, "threshold": threshold},
        )

    # User Actions
    def log_user_action(self, user_id: str, action: str, details: Optional[Dict] = None):
        self.log_event(
            EventType.USER_ACTION,
            message=f"User action: {action}",
            user_id=user_id,
            data={"action": action, "details": details or {}},
        )

    # Metrics
    def get_metrics(self) -> Dict:
        avg_response_time = (
            sum(self.metrics["response_times"]) / len(self.metrics["response_times"])
            if self.metrics["response_times"]
            else 0
        )

        return {
            "requests_total": self.metrics["requests_total"],
            "requests_success": self.metrics["requests_success"],
            "requests_error": self.metrics["requests_error"],
            "success_rate": (
                self.metrics["requests_success"] / self.metrics["requests_total"] * 100
                if self.metrics["requests_total"] > 0
                else 0
            ),
            "avg_response_time": round(avg_response_time, 3),
            "db_queries_total": self.metrics["db_queries"],
            "recent_errors": self.metrics["errors"][-10:],
        }


# Singleton
app_logger = AppLogger()
