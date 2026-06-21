from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request

from app.src.api.data.service import DataService
from app.src.api.dependencies import get_data_service
from app.src.models import ImportKind, ImportResponse, OcrRequest, SourceType
from app.src.parsing import source_type_from_filename


router = APIRouter()


@router.post("/datasets/{dataset_id}/imports", response_model=ImportResponse)
async def create_import(
    dataset_id: str,
    request: Request,
    service: DataService = Depends(get_data_service),
) -> ImportResponse:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        manual_text = form.get("manual_text")
        source_type_value = form.get("source_type")
        source_type = SourceType(str(source_type_value)) if source_type_value else None
        import_kind = _import_kind(form.get("import_kind"))
        column_mapping = _column_mapping(form.get("column_mapping"))

        if file is not None and hasattr(file, "read"):
            data = await file.read()
            filename = getattr(file, "filename", None)
            inferred_source = source_type or source_type_from_filename(filename)
            if inferred_source in {SourceType.PDF, SourceType.IMAGE}:
                record, job = service.import_asset(
                    dataset_id,
                    data=data,
                    source_type=inferred_source,
                    filename=filename or "upload",
                    content_type=getattr(file, "content_type", None),
                )
                return ImportResponse(import_record=record, job=job)
            text = data.decode("utf-8", errors="ignore")
            record, job, items, labels = service.import_text(
                dataset_id,
                text=text,
                source_type=inferred_source,
                filename=filename,
                column_mapping=column_mapping,
                import_kind=import_kind,
            )
            return ImportResponse(import_record=record, job=job, created_items=items, created_labels=labels)

        if manual_text is not None:
            record, job, items, labels = service.import_text(
                dataset_id,
                text=str(manual_text),
                source_type=source_type or (SourceType.CSV if import_kind != ImportKind.GENERIC else SourceType.TEXT),
                filename=None,
                column_mapping=column_mapping,
                import_kind=import_kind,
            )
            return ImportResponse(import_record=record, job=job, created_items=items, created_labels=labels)

    payload = await request.json()
    text = str(payload.get("text", ""))
    import_kind = _import_kind(payload.get("import_kind"))
    default_source = SourceType.CSV if import_kind != ImportKind.GENERIC else SourceType.TEXT
    payload_source = SourceType(payload.get("source_type", default_source))
    filename = payload.get("filename")
    column_mapping = _column_mapping(payload.get("column_mapping") or payload.get("mapping"))
    if payload_source in {SourceType.PDF, SourceType.IMAGE} and payload.get("data"):
        data = str(payload["data"]).encode()
        record, job = service.import_asset(
            dataset_id,
            data=data,
            source_type=payload_source,
            filename=filename or "upload",
            content_type=None,
        )
        return ImportResponse(import_record=record, job=job)
    record, job, items, labels = service.import_text(
        dataset_id,
        text=text,
        source_type=payload_source,
        filename=filename,
        column_mapping=column_mapping,
        import_kind=import_kind,
    )
    return ImportResponse(import_record=record, job=job, created_items=items, created_labels=labels)


@router.post("/datasets/{dataset_id}/ocr")
def create_ocr(
    dataset_id: str,
    payload: OcrRequest,
    service: DataService = Depends(get_data_service),
) -> dict:
    suggestions, job = service.create_ocr_suggestions(dataset_id, import_id=payload.import_id)
    return {"suggestions": suggestions, "job": job}


def _column_mapping(value: object) -> dict:
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _import_kind(value: object) -> ImportKind:
    if value is None or value == "":
        return ImportKind.GENERIC
    try:
        return ImportKind(str(value))
    except ValueError:
        return ImportKind.GENERIC
