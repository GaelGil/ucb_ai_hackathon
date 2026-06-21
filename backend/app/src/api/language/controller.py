from __future__ import annotations

from fastapi import APIRouter, Depends

from app.src.api.dependencies import get_language_service
from app.src.api.language.service import LanguageService
from app.src.models import TranslationRequest, TranslationResponse


router = APIRouter()


@router.post("/models/nahuatl/translate", response_model=TranslationResponse)
def translate(
    payload: TranslationRequest,
    service: LanguageService = Depends(get_language_service),
) -> TranslationResponse:
    result = service.translate(payload.text, payload.direction)
    return TranslationResponse(input_text=payload.text, **result.model_dump())
