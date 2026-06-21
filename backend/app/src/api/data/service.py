from __future__ import annotations

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
from app.src.database.models.label import LabelSource, LabelType
from app.src.database.models.suggestion import SuggestionStatus
from app.src.jobs import JobRunner
from app.src.parsing import parse_text_items
from app.src.providers import OCRProvider
from app.src.repositories import NotFoundError
from app.src.storage import SupabaseStorage, storage_path_for_upload


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
        record_mapping = dict(column_mapping or {})
        if import_kind != api.ImportKind.GENERIC:
            record_mapping["import_kind"] = import_kind.value
        record = ImportRecord(
            dataset_id=dataset.id,
            source_type=db_source_type,
            status=ImportStatus.processing,
            filename=filename,
            column_mapping=record_mapping,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        created_rows: list[DataRow] = []
        created_labels: list[Label] = []

        def callback(job: api.Job) -> dict:
            del job
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
            self.session.commit()
            for row in created_rows:
                self.session.refresh(row)
            for label in created_labels:
                self.session.refresh(label)
            self.session.refresh(record)
            return {
                "dataset_id": dataset.id,
                "import_id": record.id,
                "item_count": len(created_rows),
                "label_count": len(created_labels),
                **stats,
            }

        job = self.jobs.run("import", callback)
        if job.status == api.JobStatus.FAILED:
            record.status = ImportStatus.failed
            record.error = job.error
            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)
        return import_to_api(record), job, [data_row_to_text_item(row) for row in created_rows], [
            label_to_api(label) for label in created_labels
        ]

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
            row = DataRow(
                dataset_id=dataset.id,
                import_id=record.id,
                row_index=0,
                source_type=db_source_type,
                storage_bucket=bucket,
                storage_path=storage_path,
                row_metadata={"filename": filename, "content_type": content_type, "byte_count": len(data)},
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
    ) -> tuple[list[api.Suggestion], api.Job]:
        dataset = self._get_dataset(dataset_id)
        created: list[AiSuggestion] = []

        def callback(job: api.Job) -> dict:
            del job
            statement = select(DataRow).where(DataRow.dataset_id == dataset.id).where(
                DataRow.source_type.in_([DataSourceType.pdf, DataSourceType.image])
            )
            if import_id:
                statement = statement.where(DataRow.import_id == import_id)
            for row in self.session.exec(statement).all():
                asset = api.UploadedAsset(
                    dataset_id=dataset.id,
                    import_id=row.import_id or "",
                    source_type=api.SourceType(row.source_type.value),
                    filename=str(row.row_metadata.get("filename") or row.storage_path or "upload"),
                    content_type=row.row_metadata.get("content_type"),
                    data=b"",
                    created_at=row.created_at,
                )
                text, confidence, rationale = self.ocr_provider.extract(asset)
                suggestion = AiSuggestion(
                    dataset_id=dataset.id,
                    data_row_id=row.id,
                    label_type=LabelType.ocr,
                    status=SuggestionStatus.pending,
                    original_value={"text": text, "storage_path": row.storage_path},
                    confidence=confidence,
                    rationale=rationale,
                    provider="local-ocr",
                )
                self.session.add(suggestion)
                created.append(suggestion)
            self.session.commit()
            for suggestion in created:
                self.session.refresh(suggestion)
            return {"dataset_id": dataset.id, "created_count": len(created)}

        job = self.jobs.run("ocr", callback)
        from app.src.api.mappers import ai_suggestion_to_api

        return [ai_suggestion_to_api(suggestion) for suggestion in created], job

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

        if import_kind == api.ImportKind.TRANSLATION:
            return self._create_translation_csv_rows(dataset_id, import_id, headers, raw_rows)
        if import_kind == api.ImportKind.POS:
            return self._create_pos_csv_rows(dataset_id, import_id, headers, raw_rows)

        rows = [row for row in raw_rows if any((value or "").strip() for value in row.values())]
        if not rows:
            created_rows, created_labels = self._create_plain_csv_rows(dataset_id, import_id, text)
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
            self.session.flush()
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
                self.session.add(label)
                created_labels.append(label)
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
            self.session.flush()
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
            self.session.add(label)
            created_labels.append(label)
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
            self.session.flush()
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
            self.session.add(label)
            created_labels.append(label)
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
