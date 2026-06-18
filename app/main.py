from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.core.exceptions import BusinessRuleError, business_rule_handler, validation_exception_handler
from app.routers.clinic import router as clinic_router


def create_app() -> FastAPI:
    app = FastAPI(title="API Clinica Veterinaria", version="1.0.0")
    app.add_exception_handler(BusinessRuleError, business_rule_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(clinic_router)
    return app


app = create_app()
