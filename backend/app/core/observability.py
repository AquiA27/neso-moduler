# backend/app/core/observability.py
import time
import uuid
import logging
from collections import deque, defaultdict
from typing import Deque, Dict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from .config import settings

logger = logging.getLogger("neso.observability")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

class RequestIdAndRateLimitMiddleware(BaseHTTPMiddleware):
    """
    - Her isteğe X-Request-ID atar (response header'a yazar)
    - Basit IP rate limit uygular (varsayılan 60/dk)
    - Süre, durum, yol bilgisi loglar
    """
    def __init__(self, app):
        super().__init__(app)
        self.window_seconds = 60
        self.limit = int(settings.RATE_LIMIT_PER_MINUTE)
        self.hits: Dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()

        # Request-ID
        req_id = str(uuid.uuid4())
        request.state.request_id = req_id

        # Client IP (proxy yoksa direkt)
        client_ip = request.client.host if request.client else "unknown"

        # --- Rate limit ---
        now = time.time()
        q = self.hits[client_ip]
        # pencere dışındakileri düş
        while q and now - q[0] > self.window_seconds:
            q.popleft()
        if self.limit > 0 and len(q) >= self.limit:
            # Kısıt aşıldı
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests", "request_id": req_id},
                headers={"X-Request-ID": req_id} if settings.ADD_REQUEST_ID_HEADER else None,
            )
        q.append(now)

        # --- Dev log ---
        if settings.REQUEST_LOG_ENABLED:
            logger.info(
                f"[IN ] {req_id} {request.method} {request.url.path} from {client_ip}"
            )

        try:
            response: Response = await call_next(request)
        except Exception as e:
            # Hata durumunda da Request-ID header'ı basalım
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.exception(f"[ERR] {req_id} {request.method} {request.url.path} {type(e).__name__}: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal Server Error",
                    "request_id": req_id,
                },
                headers={"X-Request-ID": req_id} if settings.ADD_REQUEST_ID_HEADER else None,
            )

        # Response'a Request-ID ekle
        if settings.ADD_REQUEST_ID_HEADER:
            response.headers["X-Request-ID"] = req_id

        # Çıkış logu
        if settings.REQUEST_LOG_ENABLED:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                f"[OUT] {req_id} {request.method} {request.url.path} "
                f"-> {response.status_code} in {duration_ms}ms"
            )

        return response
