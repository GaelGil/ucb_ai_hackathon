from __future__ import annotations

import base64
import csv
import json
from io import StringIO
from typing import Any

from sqlmodel import Session, select

from app.src import models as api
from app.src.api.mappers import data_row_to_text_item, import_to_api, job_to_api, label_to_api, source_type_to_db
from app.src.database.models import AiSuggestion, DataRow, Dataset, ImportRecord, Job, Label
from app.src.database.models.data import DataSourceType
from app.src.database.models.import_record import ImportStatus
from app.src.database.models.job import JobStatus as DbJobStatus
from app.src.database.models.label import LabelSource, LabelType
from app.src.database.models.language import now_utc
from app.src.database.models.suggestion import SuggestionStatus
from app.src.jobs import JobRunner
from app.src.parsing import parse_text_items
from app.src.providers import OCRProvider
from app.src.repositories import NotFoundError
from app.src.storage import SupabaseStorage, storage_path_for_upload


CSV_IMPORT_BATCH_SIZE = 5


class DataService:
    def __init__(
        self,
        session: Session,
        ocr_provider: OCRProvider,
        jobs: JobRunner,
        storage: SupabaseStorage,
    ) -> None:
        self.session = session
        self.ocr_provider = ocr_provider
        self.jobs = jobs
        self.storage = storage

    def import_text(
        self,
        dataset_id: str,
        *,
        text: str,
        source_type: api.SourceType,
        filename: str | None = None,
        column_mapping: dict[str, Any] | None = None,
        import_kind: api.ImportKind = api.ImportKind.GENERIC,
    ) -> tuple[api.ImportRecord, api.Job, list[api.TextItem], list[api.Label]]:
        dataset = self._get_dataset(dataset_id)
        db_source_type = source_type_to_db(source_type)
        record = self._create_import_record(dataset, db_source_type, filename, column_mapping, import_kind)
        created_items: list[api.TextItem] = []
        created_label_items: list[api.Label] = []

        def callback(job: api.Job) -> dict:
            del job
            created_rows: list[DataRow] = []
            created_labels: list[Label] = []
            stats: dict[str, Any] = {"import_kind": import_kind.value, "skipped_count": 0}
            if import_kind != api.ImportKind.GENERIC and db_source_type != DataSourceType.csv:
                raise ValueError(f"{import_kind.value} imports require CSV source_type.")
            if db_source_type == DataSourceType.csv:
                rows, labels, stats = self._create_csv_rows(
                    dataset.id,
                    record.id,
                    text,
                    record.column_mapping,
                    import_kind,
                )
                created_rows.extend(rows)
                created_labels.extend(labels)
            else:
                values = parse_text_items(text, source_type)
                for index, value in enumerate(values):
                    row = DataRow(
                        dataset_id=dataset.id,
                        import_id=record.id,
                        row_index=index,
                        source_type=db_source_type,
                        text_content=value,
                    )
                    self.session.add(row)
                    created_rows.append(row)
            record.row_count = len(created_rows)
            record.label_count = len(created_labels)
            record.status = ImportStatus.ready
            self.session.add(record)
            self._commit_without_expiring_created_objects()
            self.session.refresh(record)
            created_items.extend(data_row_to_text_item(row) for row in created_rows)
            created_label_items.extend(label_to_api(label) for label in created_labels)
            return {
                "dataset_id": dataset.id,
                "import_id": record.id,
                "item_count": len(created_rows),
                "label_count": len(created_labels),
                **stats,
            }

        job = self.jobs.run("import", callback)
        if job.status == api.JobStatus.FAILED:
            if db_source_type == DataSourceType.csv:
                print(
                    "[csv-upload] error "
                    f"dataset_id={dataset.id} import_id={record.id} filename={filename or 'manual'} "
                    f"import_kind={import_kind.value} error={job.error or 'unknown error'}",
                    flush=True,
                )
            record.status = ImportStatus.failed
            record.error = job.error
            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)
        return import_to_api(record), job, created_items, created_label_items

    def queue_import_text(
        self,
        dataset_id: str,
        *,
        source_type: api.SourceType,
        filename: str | None = None,
        column_mapping: dict[str, Any] | None = None,
        import_kind: api.ImportKind = api.ImportKind.GENERIC,
    ) -> tuple[api.ImportRecord, api.Job]:
        dataset = self._get_dataset(dataset_id)
        db_source_type = source_type_to_db(source_type)
        if import_kind != api.ImportKind.GENERIC and db_source_type != DataSourceType.csv:
            raise ValueError(f"{import_kind.value} imports require CSV source_type.")
        record = self._create_import_record(dataset, db_source_type, filename, column_mapping, import_kind)
        job = Job(
            type="import",
            status=DbJobStatus.running,
            progress=5,
            message="Started",
            job_metadata={
                "dataset_id": dataset.id,
                "import_id": record.id,
                "import_kind": import_kind.value,
                "background": True,
            },
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return import_to_api(record), job_to_api(job)

    def complete_queued_import_text(
        self,
        *,
        import_id: str,
        job_id: str,
        text: str,
        source_type: api.SourceType,
        column_mapping: dict[str, Any] | None = None,
        import_kind: api.ImportKind = api.ImportKind.GENERIC,
    ) -> None:
        record = self.session.get(ImportRecord, import_id)
        if record is None:
            self._finish_import_job(job_id, DbJobStatus.failed, "Failed", f"Import {import_id} was not found.")
            return

        db_source_type = source_type_to_db(source_type)
        created_rows: list[DataRow] = []
        created_labels: list[Label] = []
        stats: dict[str, Any] = {"import_kind": import_kind.value, "skipped_count": 0}
        try:
            if import_kind != api.ImportKind.GENERIC and db_source_type != DataSourceType.csv:
                raise ValueError(f"{import_kind.value} imports require CSV source_type.")
            if db_source_type == DataSourceType.csv:
                stats = self._complete_csv_import_in_batches(
                    record=record,
                    job_id=job_id,
                    text=text,
                    column_mapping=column_mapping or record.column_mapping,
                    import_kind=import_kind,
                    batch_size=CSV_IMPORT_BATCH_SIZE,
                )
                return
            else:
                values = parse_text_items(text, source_type)
                for index, value in enumerate(values):
                    row = DataRow(
                        dataset_id=record.dataset_id,
                        import_id=record.id,
                        row_index=index,
                        source_type=db_source_type,
                        text_content=value,
                    )
                    self.session.add(row)
                    created_rows.append(row)

            record.row_count = len(created_rows)
            record.label_count = len(created_labels)
            record.status = ImportStatus.ready
            record.error = None
            record.updated_at = now_utc()
            self.session.add(record)
            self.session.commit()
            self._finish_import_job(
                job_id,
                DbJobStatus.succeeded,
                "Completed",
                None,
                {
                    "dataset_id": record.dataset_id,
                    "import_id": record.id,
                    "item_count": len(created_rows),
                    "label_count": len(created_labels),
                    **stats,
                },
            )
        except Exception as exc:
            self.session.rollback()
            error = str(exc)
            record = self.session.get(ImportRecord, import_id)
            if record is not None:
                record.status = ImportStatus.failed
                record.error = error
                record.updated_at = now_utc()
                self.session.add(record)
            print(
                "[csv-upload] error "
                f"dataset_id={record.dataset_id if record else 'unknown'} import_id={import_id} "
                f"filename={record.filename if record and record.filename else 'manual'} "
                f"import_kind={import_kind.value} error={error}",
                flush=True,
            )
            self._finish_import_job(job_id, DbJobStatus.failed, "Failed", error, stats)

    def _complete_csv_import_in_batches(
        self,
        *,
        record: ImportRecord,
        job_id: str,
        text: str,
        column_mapping: dict[str, Any],
        import_kind: api.ImportKind,
        batch_size: int,
    ) -> dict[str, Any]:
        reader = csv.DictReader(StringIO(text))
        headers = [header.strip() for header in reader.fieldnames or [] if header is not None]
        raw_rows = [self._normalized_csv_row(row) for row in reader]
        print(
            "[csv-upload] handling rows now "
            f"dataset_id={record.dataset_id} import_id={record.id} import_kind={import_kind.value} "
            f"headers={headers} raw_rows={len(raw_rows)}",
            flush=True,
        )

        rows = raw_rows
        text_column: str | None = None
        label_columns: list[tuple[LabelType, str, str]] = []
        if import_kind == api.ImportKind.TRANSLATION:
            self._require_csv_headers(headers, ["text", "translation", "source", "src", "target"], "Translation")
        elif import_kind == api.ImportKind.POS:
            self._require_csv_headers(headers, ["text", "tags"], "POS")
        else:
            rows = [row for row in raw_rows if any((value or "").strip() for value in row.values())]
            if not rows:
                return self._complete_plain_csv_import_in_batches(record, job_id, text, import_kind, batch_size)
            text_column = self._text_column(headers, column_mapping)
            label_columns = self._label_columns(headers, text_column, column_mapping)

        job = self.session.get(Job, job_id)
        total_rows = 0
        total_labels = 0
        skipped_count = 0
        batch_rows: list[DataRow] = []
        batch_labels: list[Label] = []

        for index, csv_row in enumerate(rows):
            row, labels = self._csv_objects_for_row(
                record.dataset_id,
                record.id,
                index,
                csv_row,
                import_kind,
                text_column,
                label_columns,
            )
            if row is None:
                skipped_count += 1
                continue
            self.session.add(row)
            batch_rows.append(row)
            total_rows += 1
            for label in labels:
                label.data_row = row
                self.session.add(label)
                batch_labels.append(label)
                total_labels += 1
            if len(batch_rows) >= batch_size:
                self._commit_import_batch(record, job, total_rows, total_labels, skipped_count, len(raw_rows))
                print(
                    "[csv-upload] batch submitted "
                    f"dataset_id={record.dataset_id} import_id={record.id} batch_rows={len(batch_rows)} "
                    f"batch_labels={len(batch_labels)} total_rows={total_rows} total_labels={total_labels} "
                    f"skipped={skipped_count}",
                    flush=True,
                )
                batch_rows.clear()
                batch_labels.clear()

        record.status = ImportStatus.ready
        self._commit_import_batch(record, job, total_rows, total_labels, skipped_count, len(raw_rows))
        print(
            "[csv-upload] rows submitted "
            f"dataset_id={record.dataset_id} import_id={record.id} rows={total_rows} "
            f"labels={total_labels} skipped={skipped_count}",
            flush=True,
        )
        metadata = {
            "dataset_id": record.dataset_id,
            "import_id": record.id,
            "import_kind": import_kind.value,
            "item_count": total_rows,
            "label_count": total_labels,
            "created_count": total_rows,
            "skipped_count": skipped_count,
            "batch_size": batch_size,
        }
        self._finish_import_job(job_id, DbJobStatus.succeeded, "Completed", None, metadata)
        return metadata

    def _complete_plain_csv_import_in_batches(
        self,
        record: ImportRecord,
        job_id: str,
        text: str,
        import_kind: api.ImportKind,
        batch_size: int,
    ) -> dict[str, Any]:
        job = self.session.get(Job, job_id)
        total_rows = 0
        batch_rows: list[DataRow] = []
        for index, row in enumerate(csv.reader(StringIO(text))):
            first = next((cell.strip() for cell in row if cell.strip()), "")
            if not first:
                continue
            data_row = DataRow(
                dataset_id=record.dataset_id,
                import_id=record.id,
                row_index=index,
                source_type=DataSourceType.csv,
                text_content=first,
            )
            self.session.add(data_row)
            batch_rows.append(data_row)
            total_rows += 1
            if len(batch_rows) >= batch_size:
                self._commit_import_batch(record, job, total_rows, 0, 0, total_rows)
                print(
                    "[csv-upload] batch submitted "
                    f"dataset_id={record.dataset_id} import_id={record.id} batch_rows={len(batch_rows)} "
                    f"batch_labels=0 total_rows={total_rows} total_labels=0 skipped=0",
                    flush=True,
                )
                batch_rows.clear()

        record.status = ImportStatus.ready
        self._commit_import_batch(record, job, total_rows, 0, 0, total_rows)
        print(
            "[csv-upload] rows submitted "
            f"dataset_id={record.dataset_id} import_id={record.id} rows={total_rows} labels=0 skipped=0",
            flush=True,
        )
        metadata = {
            "dataset_id": record.dataset_id,
            "import_id": record.id,
            "import_kind": import_kind.value,
            "item_count": total_rows,
            "label_count": 0,
            "created_count": total_rows,
            "skipped_count": 0,
            "batch_size": batch_size,
        }
        self._finish_import_job(job_id, DbJobStatus.succeeded, "Completed", None, metadata)
        return metadata

    def _commit_import_batch(
        self,
        record: ImportRecord,
        job: Job | None,
        total_rows: int,
        total_labels: int,
        skipped_count: int,
        raw_row_count: int,
    ) -> None:
        record.row_count = total_rows
        record.label_count = total_labels
        record.updated_at = now_utc()
        self.session.add(record)
        if job is not None:
            job.progress = min(95, 5 + int((total_rows + skipped_count) / max(raw_row_count, 1) * 90))
            job.message = f"Imported {total_rows} rows"
            job.job_metadata = {
                **(job.job_metadata or {}),
                "item_count": total_rows,
                "label_count": total_labels,
                "skipped_count": skipped_count,
                "batch_size": CSV_IMPORT_BATCH_SIZE,
            }
            job.updated_at = now_utc()
            self.session.add(job)
        self._commit_without_expiring_created_objects()

    def _csv_objects_for_row(
        self,
        dataset_id: str,
        import_id: str,
        row_index: int,
        csv_row: dict[str, str],
        import_kind: api.ImportKind,
        text_column: str | None,
        label_columns: list[tuple[LabelType, str, str]],
    ) -> tuple[DataRow | None, list[Label]]:
        if import_kind == api.ImportKind.TRANSLATION:
            text_value = (csv_row.get("text") or "").strip()
            translation = (csv_row.get("translation") or "").strip()
            if not text_value or not translation:
                return None, []
            row = self._csv_data_row(dataset_id, import_id, row_index, text_value, csv_row)
            return row, [
                Label(
                    dataset_id=dataset_id,
                    data_row_id=row.id,
                    import_id=import_id,
                    type=LabelType.translation,
                    name="translation",
                    value={
                        "text": translation,
                        "source": (csv_row.get("source") or "").strip(),
                        "src": (csv_row.get("src") or "").strip(),
                        "target": (csv_row.get("target") or "").strip(),
                    },
                    source=LabelSource.csv_import,
                    original_column_name="translation",
                )
            ]

        if import_kind == api.ImportKind.POS:
            text_value = (csv_row.get("text") or "").strip()
            tags_value = self._normalized_pos_tags(csv_row.get("tags") or "")
            tokens = text_value.split()
            tags = tags_value.split()
            if not text_value or not tags_value or len(tokens) != len(tags) or any(tag not in api.UPOS_TAGS for tag in tags):
                return None, []
            row = self._csv_data_row(dataset_id, import_id, row_index, text_value, csv_row)
            return row, [
                Label(
                    dataset_id=dataset_id,
                    data_row_id=row.id,
                    import_id=import_id,
                    type=LabelType.pos,
                    name="tags",
                    value={"tags": tags_value},
                    source=LabelSource.csv_import,
                    original_column_name="tags",
                )
            ]

        text_value = (csv_row.get(text_column) or "").strip() if text_column else self._first_value(csv_row)
        if not text_value:
            return None, []
        row = self._csv_data_row(dataset_id, import_id, row_index, text_value, csv_row)
        labels: list[Label] = []
        for label_type, name, column in label_columns:
            raw_value = (csv_row.get(column) or "").strip()
            if not raw_value:
                continue
            labels.append(
                Label(
                    dataset_id=dataset_id,
                    data_row_id=row.id,
                    import_id=import_id,
                    type=label_type,
                    name=name,
                    value=self._label_value(raw_value, label_type),
                    source=LabelSource.csv_import,
                    original_column_name=column,
                )
            )
        return row, labels

    def _csv_data_row(
        self,
        dataset_id: str,
        import_id: str,
        row_index: int,
        text_value: str,
        csv_row: dict[str, str],
    ) -> DataRow:
        return DataRow(
            dataset_id=dataset_id,
            import_id=import_id,
            row_index=row_index,
            source_type=DataSourceType.csv,
            text_content=text_value,
            row_metadata={"csv": csv_row},
        )

    def _create_import_record(
        self,
        dataset: Dataset,
        source_type: DataSourceType,
        filename: str | None,
        column_mapping: dict[str, Any] | None,
        import_kind: api.ImportKind,
    ) -> ImportRecord:
        record_mapping = dict(column_mapping or {})
        if import_kind != api.ImportKind.GENERIC:
            record_mapping["import_kind"] = import_kind.value
        record = ImportRecord(
            dataset_id=dataset.id,
            source_type=source_type,
            status=ImportStatus.processing,
            filename=filename,
            column_mapping=record_mapping,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def _commit_without_expiring_created_objects(self) -> None:
        expire_on_commit = self.session.expire_on_commit
        self.session.expire_on_commit = False
        try:
            self.session.commit()
        finally:
            self.session.expire_on_commit = expire_on_commit

    def _finish_import_job(
        self,
        job_id: str,
        status: DbJobStatus,
        message: str,
        error: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        job = self.session.get(Job, job_id)
        if job is None:
            return
        job.status = status
        job.progress = 100
        job.message = message
        job.error = error
        job.job_metadata = {**(job.job_metadata or {}), **(metadata or {})}
        job.updated_at = now_utc()
        self.session.add(job)
        self.session.commit()

    def import_asset(
        self,
        dataset_id: str,
        *,
        data: bytes,
        source_type: api.SourceType,
        filename: str,
        content_type: str | None,
    ) -> tuple[api.ImportRecord, api.Job]:
        dataset = self._get_dataset(dataset_id)
        db_source_type = source_type_to_db(source_type)
        record = ImportRecord(
            dataset_id=dataset.id,
            source_type=db_source_type,
            status=ImportStatus.processing,
            filename=filename,
            content_type=content_type,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)

        def callback(job: api.Job) -> dict:
            del job
            path = storage_path_for_upload(dataset.id, record.id, filename)
            bucket, storage_path = self.storage.upload(path=path, data=data, content_type=content_type)
            row_metadata: dict[str, Any] = {"filename": filename, "content_type": content_type, "byte_count": len(data)}
            if db_source_type == DataSourceType.image and not self.storage.is_configured:
                row_metadata["inline_data_base64"] = base64.b64encode(data).decode("ascii")
            row = DataRow(
                dataset_id=dataset.id,
                import_id=record.id,
                row_index=0,
                source_type=db_source_type,
                storage_bucket=bucket,
                storage_path=storage_path,
                row_metadata=row_metadata,
            )
            self.session.add(row)
            record.storage_bucket = bucket
            record.storage_path = storage_path
            record.row_count = 1
            record.status = ImportStatus.ready
            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)
            return {"dataset_id": dataset.id, "import_id": record.id, "asset_count": 1}

        job = self.jobs.run("import_asset", callback)
        if job.status == api.JobStatus.FAILED:
            record.status = ImportStatus.failed
            record.error = job.error
            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)
        return import_to_api(record), job

    def create_ocr_suggestions(
        self,
        dataset_id: str,
        import_id: str | None = None,
        import_ids: list[str] | None = None,
    ) -> tuple[list[api.Suggestion], api.Job]:
        dataset = self._get_dataset(dataset_id)
        created: list[AiSuggestion] = []

        def callback(job: api.Job) -> dict:
            del job
            rows, metadata = self._create_ocr_suggestion_rows(dataset, import_id=import_id, import_ids=import_ids)
            created.extend(rows)
            return metadata

        job = self.jobs.run("ocr", callback)
        from app.src.api.mappers import ai_suggestion_to_api

        return [ai_suggestion_to_api(suggestion) for suggestion in created], job

    def queue_ocr_suggestions(
        self,
        dataset_id: str,
        import_id: str | None = None,
        import_ids: list[str] | None = None,
    ) -> tuple[list[api.Suggestion], api.Job]:
        dataset = self._get_dataset(dataset_id)
        selected_import_ids = self._selected_import_ids(import_id=import_id, import_ids=import_ids)
        job = self.jobs.create_running(
            "ocr",
            metadata={
                "dataset_id": dataset.id,
                "import_ids": sorted(selected_import_ids) if selected_import_ids else [],
                "provider": getattr(self.ocr_provider, "provider", "anthropic"),
                "model": getattr(self.ocr_provider, "model_name", None),
            },
            message="OCR started",
        )
        return [], job

    def complete_queued_ocr_suggestions(
        self,
        *,
        job_id: str,
        dataset_id: str,
        import_id: str | None = None,
        import_ids: list[str] | None = None,
    ) -> api.Job:
        dataset = self._get_dataset(dataset_id)

        def callback(job: api.Job) -> dict:
            del job
            _, metadata = self._create_ocr_suggestion_rows(dataset, import_id=import_id, import_ids=import_ids)
            return metadata

        return self.jobs.run_existing(job_id, callback)

    def _create_ocr_suggestion_rows(
        self,
        dataset: Dataset,
        *,
        import_id: str | None = None,
        import_ids: list[str] | None = None,
    ) -> tuple[list[AiSuggestion], dict[str, Any]]:
        selected_import_ids = self._selected_import_ids(import_id=import_id, import_ids=import_ids)
        statement = select(DataRow).where(DataRow.dataset_id == dataset.id).where(DataRow.source_type == DataSourceType.image)
        if selected_import_ids:
            statement = statement.where(DataRow.import_id.in_(sorted(selected_import_ids)))
        rows = self.session.exec(statement).all()
        if not rows:
            raise RuntimeError("Select at least one uploaded image before running OCR.")

        created: list[AiSuggestion] = []
        evaluations: list[dict[str, Any]] = []
        with self.jobs.tracer.span(
            "ocr.suggestions.create",
            dataset_id=dataset.id,
            import_count=len(selected_import_ids) if selected_import_ids else "all",
            image_count=len(rows),
        ):
            for row in rows:
                asset = api.UploadedAsset(
                    dataset_id=dataset.id,
                    import_id=row.import_id or "",
                    source_type=api.SourceType(row.source_type.value),
                    filename=str(row.row_metadata.get("filename") or row.storage_path or "upload"),
                    content_type=row.row_metadata.get("content_type"),
                    data=self._asset_bytes(row),
                    created_at=row.created_at,
                )
                text, confidence, rationale = self.ocr_provider.extract(asset)
                evaluation = self._evaluate_ocr(asset, text, confidence, rationale, dataset.id, row.id)
                if evaluation:
                    evaluations.append(evaluation)
                suggestion = AiSuggestion(
                    dataset_id=dataset.id,
                    data_row_id=row.id,
                    label_type=LabelType.ocr,
                    status=SuggestionStatus.pending,
                    original_value={
                        "text": text,
                        "storage_path": row.storage_path,
                        "filename": asset.filename,
                        "metadata": {"evaluation": evaluation} if evaluation else {},
                    },
                    confidence=confidence,
                    rationale=rationale,
                    provider=getattr(self.ocr_provider, "provider", "anthropic"),
                    model_name=getattr(self.ocr_provider, "model_name", None),
                )
                self.session.add(suggestion)
                created.append(suggestion)
        self.session.commit()
        for suggestion in created:
            self.session.refresh(suggestion)
        return created, {
            "dataset_id": dataset.id,
            "created_count": len(created),
            "import_ids": sorted(selected_import_ids) if selected_import_ids else [],
            "provider": getattr(self.ocr_provider, "provider", "anthropic"),
            "model": getattr(self.ocr_provider, "model_name", None),
            "evaluation": self._evaluation_summary(evaluations),
        }

    def _evaluate_ocr(
        self,
        asset: api.UploadedAsset,
        text: str,
        confidence: float,
        rationale: str,
        dataset_id: str,
        row_id: str,
    ) -> dict[str, Any]:
        evaluator = getattr(self.ocr_provider, "evaluate", None)
        if evaluator is None:
            return {}
        try:
            evaluation = evaluator(asset, text, confidence, rationale)
        except Exception as exc:
            evaluation = {"name": "ocr_quality", "kind": "llm", "label": "error", "feedback": str(exc)}
        self.jobs.tracer.record_evaluation(
            "ocr_quality",
            evaluation,
            dataset_id=dataset_id,
            data_row_id=row_id,
            import_id=asset.import_id,
        )
        return evaluation

    def _evaluation_summary(self, evaluations: list[dict[str, Any]]) -> dict[str, Any]:
        if not evaluations:
            return {}
        scores = [float(item["score"]) for item in evaluations if isinstance(item.get("score"), (int, float))]
        return {
            "count": len(evaluations),
            "average_score": round(sum(scores) / len(scores), 3) if scores else None,
            "labels": [item.get("label") for item in evaluations if item.get("label")],
            "feedback": [item.get("feedback") for item in evaluations if item.get("feedback")],
        }

    def _asset_bytes(self, row: DataRow) -> bytes:
        inline = row.row_metadata.get("inline_data_base64") if isinstance(row.row_metadata, dict) else None
        if inline:
            return base64.b64decode(str(inline))
        if row.storage_bucket and row.storage_path:
            return self.storage.download(bucket=row.storage_bucket, path=row.storage_path)
        raise RuntimeError("Uploaded image bytes are not available for OCR.")

    def _selected_import_ids(self, *, import_id: str | None, import_ids: list[str] | None) -> set[str]:
        selected = {value for value in (import_ids or []) if value}
        if import_id:
            selected.add(import_id)
        return selected

    def _create_csv_rows(
        self,
        dataset_id: str,
        import_id: str,
        text: str,
        column_mapping: dict[str, Any],
        import_kind: api.ImportKind,
    ) -> tuple[list[DataRow], list[Label], dict[str, Any]]:
        reader = csv.DictReader(StringIO(text))
        headers = [header.strip() for header in reader.fieldnames or [] if header is not None]
        raw_rows = [self._normalized_csv_row(row) for row in reader]
        print(
            "[csv-upload] handling rows now "
            f"dataset_id={dataset_id} import_id={import_id} import_kind={import_kind.value} "
            f"headers={headers} raw_rows={len(raw_rows)}",
            flush=True,
        )

        if import_kind == api.ImportKind.TRANSLATION:
            return self._create_translation_csv_rows(dataset_id, import_id, headers, raw_rows)
        if import_kind == api.ImportKind.POS:
            return self._create_pos_csv_rows(dataset_id, import_id, headers, raw_rows)

        rows = [row for row in raw_rows if any((value or "").strip() for value in row.values())]
        if not rows:
            created_rows, created_labels = self._create_plain_csv_rows(dataset_id, import_id, text)
            print(
                "[csv-upload] rows submitted "
                f"dataset_id={dataset_id} import_id={import_id} rows={len(created_rows)} "
                f"labels={len(created_labels)} skipped=0",
                flush=True,
            )
            return created_rows, created_labels, {
                "import_kind": import_kind.value,
                "created_count": len(created_rows),
                "label_count": len(created_labels),
                "skipped_count": 0,
            }

        text_column = self._text_column(headers, column_mapping)
        label_columns = self._label_columns(headers, text_column, column_mapping)
        created_rows: list[DataRow] = []
        created_labels: list[Label] = []
        skipped_count = 0
        for index, csv_row in enumerate(rows):
            text_value = (csv_row.get(text_column) or "").strip() if text_column else self._first_value(csv_row)
            if not text_value:
                skipped_count += 1
                continue
            row = DataRow(
                dataset_id=dataset_id,
                import_id=import_id,
                row_index=index,
                source_type=DataSourceType.csv,
                text_content=text_value,
                row_metadata={"csv": csv_row},
            )
            self.session.add(row)
            created_rows.append(row)
            for label_type, name, column in label_columns:
                raw_value = (csv_row.get(column) or "").strip()
                if not raw_value:
                    continue
                label = Label(
                    dataset_id=dataset_id,
                    data_row_id=row.id,
                    import_id=import_id,
                    type=label_type,
                    name=name,
                    value=self._label_value(raw_value, label_type),
                    source=LabelSource.csv_import,
                    original_column_name=column,
                )
                label.data_row = row
                self.session.add(label)
                created_labels.append(label)
        print(
            "[csv-upload] rows submitted "
            f"dataset_id={dataset_id} import_id={import_id} rows={len(created_rows)} "
            f"labels={len(created_labels)} skipped={skipped_count}",
            flush=True,
        )
        return created_rows, created_labels, {
            "import_kind": import_kind.value,
            "created_count": len(created_rows),
            "label_count": len(created_labels),
            "skipped_count": skipped_count,
        }

    def _create_translation_csv_rows(
        self,
        dataset_id: str,
        import_id: str,
        headers: list[str],
        rows: list[dict[str, str]],
    ) -> tuple[list[DataRow], list[Label], dict[str, Any]]:
        required = ["text", "translation", "source", "src", "target"]
        self._require_csv_headers(headers, required, "Translation")
        created_rows: list[DataRow] = []
        created_labels: list[Label] = []
        skipped_count = 0
        for index, csv_row in enumerate(rows):
            text_value = (csv_row.get("text") or "").strip()
            translation = (csv_row.get("translation") or "").strip()
            if not text_value or not translation:
                skipped_count += 1
                continue
            row = DataRow(
                dataset_id=dataset_id,
                import_id=import_id,
                row_index=index,
                source_type=DataSourceType.csv,
                text_content=text_value,
                row_metadata={"csv": csv_row},
            )
            self.session.add(row)
            created_rows.append(row)
            label = Label(
                dataset_id=dataset_id,
                data_row_id=row.id,
                import_id=import_id,
                type=LabelType.translation,
                name="translation",
                value={
                    "text": translation,
                    "source": (csv_row.get("source") or "").strip(),
                    "src": (csv_row.get("src") or "").strip(),
                    "target": (csv_row.get("target") or "").strip(),
                },
                source=LabelSource.csv_import,
                original_column_name="translation",
            )
            label.data_row = row
            self.session.add(label)
            created_labels.append(label)
        print(
            "[csv-upload] rows submitted "
            f"dataset_id={dataset_id} import_id={import_id} rows={len(created_rows)} "
            f"labels={len(created_labels)} skipped={skipped_count}",
            flush=True,
        )
        return created_rows, created_labels, {
            "import_kind": api.ImportKind.TRANSLATION.value,
            "created_count": len(created_rows),
            "label_count": len(created_labels),
            "skipped_count": skipped_count,
        }

    def _create_pos_csv_rows(
        self,
        dataset_id: str,
        import_id: str,
        headers: list[str],
        rows: list[dict[str, str]],
    ) -> tuple[list[DataRow], list[Label], dict[str, Any]]:
        required = ["text", "tags"]
        self._require_csv_headers(headers, required, "POS")
        created_rows: list[DataRow] = []
        created_labels: list[Label] = []
        skipped_count = 0
        for index, csv_row in enumerate(rows):
            text_value = (csv_row.get("text") or "").strip()
            tags_value = self._normalized_pos_tags(csv_row.get("tags") or "")
            tokens = text_value.split()
            tags = tags_value.split()
            if not text_value or not tags_value or len(tokens) != len(tags) or any(tag not in api.UPOS_TAGS for tag in tags):
                skipped_count += 1
                continue
            row = DataRow(
                dataset_id=dataset_id,
                import_id=import_id,
                row_index=index,
                source_type=DataSourceType.csv,
                text_content=text_value,
                row_metadata={"csv": csv_row},
            )
            self.session.add(row)
            created_rows.append(row)
            label = Label(
                dataset_id=dataset_id,
                data_row_id=row.id,
                import_id=import_id,
                type=LabelType.pos,
                name="tags",
                value={"tags": tags_value},
                source=LabelSource.csv_import,
                original_column_name="tags",
            )
            label.data_row = row
            self.session.add(label)
            created_labels.append(label)
        print(
            "[csv-upload] rows submitted "
            f"dataset_id={dataset_id} import_id={import_id} rows={len(created_rows)} "
            f"labels={len(created_labels)} skipped={skipped_count}",
            flush=True,
        )
        return created_rows, created_labels, {
            "import_kind": api.ImportKind.POS.value,
            "created_count": len(created_rows),
            "label_count": len(created_labels),
            "skipped_count": skipped_count,
        }

    def _create_plain_csv_rows(self, dataset_id: str, import_id: str, text: str) -> tuple[list[DataRow], list[Label]]:
        created: list[DataRow] = []
        for index, row in enumerate(csv.reader(StringIO(text))):
            first = next((cell.strip() for cell in row if cell.strip()), "")
            if not first:
                continue
            data_row = DataRow(
                dataset_id=dataset_id,
                import_id=import_id,
                row_index=index,
                source_type=DataSourceType.csv,
                text_content=first,
            )
            self.session.add(data_row)
            created.append(data_row)
        return created, []

    def _normalized_csv_row(self, row: dict[str | None, str | None]) -> dict[str, str]:
        return {str(key).strip(): str(value or "") for key, value in row.items() if key is not None}

    def _require_csv_headers(self, headers: list[str], required: list[str], label: str) -> None:
        missing = [header for header in required if header not in headers]
        if missing:
            raise ValueError(
                f"{label} CSV requires columns: {','.join(required)}. Missing columns: {','.join(missing)}."
            )

    def _normalized_pos_tags(self, raw_value: str) -> str:
        value = raw_value.strip()
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value
        if isinstance(parsed, list):
            value = " ".join(str(item).strip() for item in parsed if str(item).strip())
        return " ".join(tag.upper() for tag in value.split())

    def _text_column(self, headers: list[str], column_mapping: dict[str, Any]) -> str | None:
        explicit = column_mapping.get("text") or column_mapping.get("text_column")
        if explicit in headers:
            return str(explicit)
        preferred = ["text", "sentence", "sentences", "utterance", "content", "source_text"]
        return next((header for header in preferred if header in headers), headers[0] if headers else None)

    def _label_columns(
        self,
        headers: list[str],
        text_column: str | None,
        column_mapping: dict[str, Any],
    ) -> list[tuple[LabelType, str, str]]:
        configured = column_mapping.get("labels") or column_mapping.get("label_columns")
        if isinstance(configured, dict):
            columns: list[tuple[LabelType, str, str]] = []
            for raw_type, raw_columns in configured.items():
                selected_columns = raw_columns if isinstance(raw_columns, list) else [raw_columns]
                for column in selected_columns:
                    if column in headers:
                        columns.append((self._infer_label_type(str(raw_type)), str(raw_type), str(column)))
            return columns
        if isinstance(configured, list):
            return [
                (self._infer_label_type(str(column)), str(column), str(column))
                for column in configured
                if column in headers and column != text_column
            ]

        skipped = {text_column, "id", "row_id", "uuid", "language", "language_code", "language_name", None}
        return [
            (self._infer_label_type(header), header, header)
            for header in headers
            if header not in skipped and not header.lower().startswith("metadata")
        ]

    def _infer_label_type(self, value: str) -> LabelType:
        normalized = value.lower().replace("-", "_").replace(" ", "_")
        if "translation" in normalized or normalized in {"target", "target_text"}:
            return LabelType.translation
        if "pos" in normalized or "tag" in normalized or "upos" in normalized:
            return LabelType.pos
        if "ocr" in normalized or "character" in normalized:
            return LabelType.ocr
        if "emotion" in normalized:
            return LabelType.emotion
        if "intent" in normalized or "intention" in normalized:
            return LabelType.intention
        return LabelType.custom

    def _label_value(self, raw_value: str, label_type: LabelType) -> dict[str, Any]:
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            parsed = raw_value
        if isinstance(parsed, dict):
            return parsed
        if label_type == LabelType.pos and isinstance(parsed, list):
            return {"tags": self._normalized_pos_tags(json.dumps(parsed))}
        return {"text": str(parsed)}

    def _first_value(self, row: dict[str, str]) -> str:
        return next((value.strip() for value in row.values() if value and value.strip()), "")

    def _get_dataset(self, dataset_id: str) -> Dataset:
        dataset = self.session.get(Dataset, dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset {dataset_id} was not found.")
        return dataset
