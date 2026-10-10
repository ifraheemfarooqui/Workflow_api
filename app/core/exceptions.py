# app/core/exceptions.py
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

logger = logging.getLogger("workflow_api")


async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error("Integrity error (%s)", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "This operation conflicts with existing data"},
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Database error (%s)", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred"},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception (%s)", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred"},
    )