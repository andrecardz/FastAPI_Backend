from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class BusinessRuleError(Exception):
    def __init__(
        self,
        error: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error = error
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def error_payload(error: str, message: str, details: dict[str, Any] | list[Any] | None = None) -> dict[str, Any]:
    return {"error": error, "message": message, "details": details or {}}


def serialize_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe_errors: list[dict[str, Any]] = []
    for error in errors:
        safe_error = dict(error)
        if "ctx" in safe_error:
            safe_error["ctx"] = {key: str(value) for key, value in safe_error["ctx"].items()}
        safe_errors.append(safe_error)
    return safe_errors


async def business_rule_handler(request: Request, exc: BusinessRuleError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.error, exc.message, exc.details),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload(
            "VALIDATION_ERROR",
            "Os dados enviados nao passaram na validacao.",
            serialize_validation_errors(exc.errors()),
        ),
    )
