from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.src.api.data.service import DataService
from app.src.api.dependencies import get_data_service
from app.src.models import ImportResponse, OcrRequest, SourceType
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
            record, job, items = service.import_text(
                dataset_id,
                text=text,
                source_type=inferred_source,
                filename=filename,
            )
            return ImportResponse(import_record=record, job=job, created_items=items)

        if manual_text is not None:
            record, job, items = service.import_text(
                dataset_id,
                text=str(manual_text),
                source_type=source_type or SourceType.TEXT,
                filename=None,
            )
            return ImportResponse(import_record=record, job=job, created_items=items)

    payload = await request.json()
    text = str(payload.get("text", ""))
    payload_source = SourceType(payload.get("source_type", SourceType.TEXT))
    filename = payload.get("filename")
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
    record, job, items = service.import_text(dataset_id, text=text, source_type=payload_source, filename=filename)
    return ImportResponse(import_record=record, job=job, created_items=items)


@router.post("/datasets/{dataset_id}/ocr")
def create_ocr(
    dataset_id: str,
    payload: OcrRequest,
    service: DataService = Depends(get_data_service),
) -> dict:
    suggestions, job = service.create_ocr_suggestions(dataset_id, import_id=payload.import_id)
    return {"suggestions": suggestions, "job": job}
