import uuid
import contextvars
import logging
import json
import time
import os
from datetime import datetime, timezone
from typing import Dict, Any
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

APP_NAME = "vibarr"
_debug_enabled = os.environ.get("LOG_LEVEL", "INFO").upper() == "DEBUG" or os.environ.get("DEBUG_LOGGING", "").lower() in ("true", "1")

# Context variable to hold the correlation ID for the current thread/coroutine context
_correlation_id_ctx = contextvars.ContextVar('correlation_id', default='-')

def get_correlation_id() -> str:
    return _correlation_id_ctx.get()

class LokiJsonFormatter(logging.Formatter):
    """Outputs standardized single-line JSON log events for Loki ingestion."""
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "app": APP_NAME,
            "logger": record.name,
            "correlation_id": getattr(record, "correlation_id", get_correlation_id()),
            "action": getattr(record, "action", "general"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        context = getattr(record, "context", None)
        if context:
            log_entry["context"] = context
        return json.dumps(log_entry)

def set_debug_logging(enabled: bool):
    global _debug_enabled
    _debug_enabled = enabled
    target_level = logging.DEBUG if enabled else logging.INFO
    for name in ["django", "vibarr", "vibarr_core", "django_q", ""]:
        logging.getLogger(name).setLevel(target_level)
    logging.getLogger("vibarr").info(
        f"[Observability] - Debug logging dynamically set to {enabled}",
        extra={"action": "observability.toggle_debug"}
    )

def is_debug_enabled() -> bool:
    return _debug_enabled

# In-memory Prometheus Metrics Registry for Vibarr
class VibarrMetrics:
    def __init__(self):
        self.requests_total: Dict[str, int] = {}
        self.actions_total: Dict[str, int] = {}
        self.start_time = time.time()

    def record_request(self, method: str, path: str, status: int):
        normalized = path.split("?")[0]
        key = f'{APP_NAME}_http_requests_total{{method="{method}",path="{normalized}",status="{status}"}}'
        self.requests_total[key] = self.requests_total.get(key, 0) + 1

    def record_action(self, action: str, status: str = "success"):
        key = f'{APP_NAME}_actions_total{{action="{action}",status="{status}"}}'
        self.actions_total[key] = self.actions_total.get(key, 0) + 1

    def generate_metrics(self) -> str:
        lines = [
            f"# HELP {APP_NAME}_uptime_seconds Process uptime in seconds",
            f"# TYPE {APP_NAME}_uptime_seconds gauge",
            f"{APP_NAME}_uptime_seconds {round(time.time() - self.start_time, 2)}",
            f"# HELP {APP_NAME}_http_requests_total Total HTTP requests handled",
            f"# TYPE {APP_NAME}_http_requests_total counter"
        ]
        for k, v in sorted(self.requests_total.items()):
            lines.append(f"{k} {v}")
        lines.append(f"# HELP {APP_NAME}_actions_total Total domain actions executed")
        lines.append(f"# TYPE {APP_NAME}_actions_total counter")
        for k, v in sorted(self.actions_total.items()):
            lines.append(f"{k} {v}")
        return "\n".join(lines) + "\n"

metrics = VibarrMetrics()
logger = logging.getLogger("vibarr.requests")

class CorrelationIDMiddleware:
    """
    Middleware that reads/generates a correlation ID for each request,
    stores it in contextvars, records Prometheus metrics, and returns it in the response headers.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        correlation_id = request.headers.get('X-Correlation-ID') or request.headers.get('X-Request-ID') or str(uuid.uuid4())
        token = _correlation_id_ctx.set(correlation_id)
        request.correlation_id = correlation_id
        start_time = time.perf_counter()

        response = self.get_response(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response['X-Correlation-ID'] = correlation_id

        metrics.record_request(request.method, request.path, response.status_code)
        if not request.path.endswith("/metrics"):
            logger.info(
                f"{request.method} {request.path} -> {response.status_code} ({duration_ms}ms)",
                extra={
                    "action": "http.request",
                    "correlation_id": correlation_id,
                    "context": {"method": request.method, "path": request.path, "status": response.status_code, "duration_ms": duration_ms}
                }
            )

        _correlation_id_ctx.reset(token)
        return response

class CorrelationIDFilter(logging.Filter):
    """
    Logging filter that injects the current context's correlation ID into the log record.
    """
    def filter(self, record):
        record.correlation_id = get_correlation_id()
        if not hasattr(record, "action"):
            record.action = "general"
        return True

@require_http_methods(["GET"])
def metrics_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse(
        metrics.generate_metrics(),
        content_type="text/plain; version=0.0.4; charset=utf-8"
    )

@csrf_exempt
@require_http_methods(["GET", "POST"])
def debug_logging_toggle_api(request: HttpRequest) -> JsonResponse:
    if request.method == "POST":
        try:
            body = json.loads(request.body.decode('utf-8'))
            enabled = bool(body.get('enabled', False))
            set_debug_logging(enabled)
            return JsonResponse({'debug_enabled': is_debug_enabled(), 'message': f'Debug logging set to {enabled}'})
        except Exception as e:
            return JsonResponse({'error': f'Invalid request: {e}'}, status=400)
    return JsonResponse({'debug_enabled': is_debug_enabled()})
