from __future__ import annotations

from flask import Blueprint, request

from app.routes.container import get_language_service
from app.routes.responses import json_response
from app.schemas import TranslationRequest, TranslationResponse


bp = Blueprint("language", __name__)


@bp.post("/models/nahuatl/translate")
def translate():
    payload = TranslationRequest.model_validate(request.get_json(silent=True) or {})
    result = get_language_service().translate(payload.text, payload.direction)
    return json_response(TranslationResponse(input_text=payload.text, **result.model_dump()))
