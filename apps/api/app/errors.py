"""RFC 9457 problem+json errors with a stable `code`, matching docs/api/openapi.yaml."""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM = "application/problem+json"
DEFAULT_CODES = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    503: "SERVICE_UNAVAILABLE",
}


class ApiError(Exception):
    """Raise from handlers: `raise ApiError(404, "NOT_FOUND", "Job not found")`."""

    def __init__(self, status: int, code: str, detail: str | None = None) -> None:
        self.status, self.code, self.detail = status, code, detail


def problem(request: Request, status: int, code: str, detail: str | None = None, **extra) -> JSONResponse:
    body = {
        "type": f"https://docs.vysel.app/errors/{code.lower().replace('_', '-')}",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "code": code,
        "instance": request.url.path,
        **({"detail": detail} if detail else {}),
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type=PROBLEM)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return problem(request, exc.status, exc.code, exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        return problem(
            request, exc.status_code, DEFAULT_CODES.get(exc.status_code, "INTERNAL_ERROR"), str(exc.detail) if exc.detail else None
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        errors = [
            {
                "field": ".".join(str(p) for p in err["loc"] if p not in ("body", "query", "path")),
                "message": err["msg"],
                "code": err["type"],
            }
            for err in exc.errors()
        ]
        return problem(request, 422, "VALIDATION_ERROR", "One or more fields are invalid.", errors=errors)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # Never leak internals; details go to logs only.
        return problem(request, 500, "INTERNAL_ERROR", "Something went wrong. Please try again.")
