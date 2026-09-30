from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

# Chỉ chấp nhận correlation_id từ client ở dạng chữ/số, dấu phân cách an toàn.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Xoá contextvars cũ để không rò correlation_id/metadata
        #    giữa các request chạy tuần tự trong cùng context.
        clear_contextvars()

        # 2. Nhận header x-request-id hợp lệ từ client;
        #    nếu không có thì sinh ID mới dạng req-<8 ký tự hex>.
        incoming = request.headers.get("x-request-id", "").strip()
        if _SAFE_REQUEST_ID.match(incoming):
            correlation_id = incoming
        else:
            correlation_id = f"req-{uuid.uuid4().hex[:8]}"

        # 3. Bind correlation_id vào structlog contextvars để mọi log
        #    trong request này (middleware, handler, error) đều gắn ID.
        bind_contextvars(correlation_id=correlation_id)

        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)

        # 4. Trả correlation_id và thời gian xử lý về client qua response header.
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = f"{elapsed_ms:.2f}"

        return response
