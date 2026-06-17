import uuid
import contextvars
import logging
from django.http import HttpRequest, HttpResponse

# Context variable to hold the correlation ID for the current thread/coroutine context
_correlation_id_ctx = contextvars.ContextVar('correlation_id', default='-')

def get_correlation_id() -> str:
    return _correlation_id_ctx.get()

class CorrelationIDMiddleware:
    """
    Middleware that reads/generates a correlation ID for each request,
    stores it in contextvars, and returns it in the response headers.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Read correlation ID from headers or generate a new one
        correlation_id = request.headers.get('X-Correlation-ID') or request.headers.get('X-Request-ID')
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Set the contextvar value
        token = _correlation_id_ctx.set(correlation_id)
        
        # Attach to request object for easy access in views
        request.correlation_id = correlation_id
        
        response = self.get_response(request)
        
        # Set response header
        response['X-Correlation-ID'] = correlation_id
        
        # Reset contextvar value
        _correlation_id_ctx.reset(token)
        return response

class CorrelationIDFilter(logging.Filter):
    """
    Logging filter that injects the current context's correlation ID into the log record.
    """
    def filter(self, record):
        record.correlation_id = get_correlation_id()
        return True
