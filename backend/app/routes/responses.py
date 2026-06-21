from __future__ import annotations

from typing import Any, NoReturn

from flask import abort, jsonify, make_response
from flask.wrappers import Response
from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    """Recursively convert Pydantic models (and containers of them) to JSON-safe data.

    Replaces FastAPI's ``response_model`` serialization. ``model_dump(mode="json")``
    already recurses into nested models, so this only needs to walk plain dicts and
    lists that hold models (e.g. ``{"suggestions": [...], "job": job}``).
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def json_response(payload: Any, status_code: int = 200) -> tuple[Response, int]:
    return jsonify(to_jsonable(payload)), status_code


def json_abort(status_code: int, detail: str) -> NoReturn:
    """Abort the request with a FastAPI-style ``{"detail": ...}`` JSON body."""
    abort(make_response(jsonify(detail=detail), status_code))
