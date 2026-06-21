from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.database.models  # noqa: F401  (registers SQLModel tables)
from app.database.models import DataRow, Dataset, ImportRecord, Label, Language
from app.database.models.data import DataSourceType
from app.database.models.label import LabelType
from app.database.session import engine


SCRIPT_NAME = "create_pos_rows_from_translation.py"


@dataclass
class PosSeedSummary:
    dataset_id: str
    dataset_name: str
    language_code: str
    translation_rows_found: int
    rows_created: int
    duplicates_skipped: int
    limit: int
    dry_run: bool


def create_pos_rows_from_translation(
    session: Session,
    *,
    dataset_ids: list[str] | None = None,
    language_codes: list[str] | None = None,
    limit: int = 100,
    dry_run: bool = False,
) -> list[PosSeedSummary]:
    if limit <= 0:
        raise ValueError("limit must be greater than 0")

    datasets = _selected_datasets(session, dataset_ids=dataset_ids, language_codes=language_codes)
    summaries: list[PosSeedSummary] = []

    for dataset in datasets:
        language = session.get(Language, dataset.language_id)
        language_code = language.code if language else "unknown"
        translation_rows = _translation_rows_for_dataset(session, dataset.id)[:limit]
        existing_source_ids = _existing_pos_seed_source_ids(session, dataset.id)
        rows_to_create = [row for row in translation_rows if row.id not in existing_source_ids]
        duplicates_skipped = len(translation_rows) - len(rows_to_create)

        if rows_to_create and not dry_run:
            import_record = ImportRecord(
                dataset_id=dataset.id,
                source_type=DataSourceType.csv,
                filename=f"pos-seed-from-translation-{language_code}.csv",
                row_count=len(rows_to_create),
                label_count=0,
                column_mapping={
                    "import_kind": "pos_seed_from_translation",
                    "source": "translation_rows",
                    "script": SCRIPT_NAME,
                },
            )
            session.add(import_record)
            session.flush()

            next_row_index = _next_row_index(session, dataset.id)
            for offset, source_row in enumerate(rows_to_create):
                metadata = dict(source_row.row_metadata or {})
                seed_row = DataRow(
                    dataset_id=dataset.id,
                    import_id=import_record.id,
                    row_index=next_row_index + offset,
                    source_type=DataSourceType.csv,
                    text_content=source_row.text_content,
                    row_metadata={
                        "csv": {"text": source_row.text_content or "", "tags": ""},
                        "pos_seed": {
                            "source": "translation_rows",
                            "source_data_row_id": source_row.id,
                            "source_import_id": source_row.import_id,
                            "script": SCRIPT_NAME,
                        },
                        "source_row_metadata": metadata,
                    },
                )
                session.add(seed_row)
            session.commit()

        summaries.append(
            PosSeedSummary(
                dataset_id=dataset.id,
                dataset_name=dataset.name,
                language_code=language_code,
                translation_rows_found=len(translation_rows),
                rows_created=len(rows_to_create) if not dry_run else 0,
                duplicates_skipped=duplicates_skipped,
                limit=limit,
                dry_run=dry_run,
            )
        )

    return summaries


def _selected_datasets(
    session: Session,
    *,
    dataset_ids: list[str] | None,
    language_codes: list[str] | None,
) -> list[Dataset]:
    selected: list[Dataset] = []
    seen_ids: set[str] = set()

    for dataset_id in dataset_ids or []:
        dataset = session.get(Dataset, dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {dataset_id} was not found.")
        if dataset.id not in seen_ids:
            selected.append(dataset)
            seen_ids.add(dataset.id)

    for language_code in language_codes or []:
        datasets = session.exec(
            select(Dataset)
            .join(Language, Dataset.language_id == Language.id)
            .where(Language.code == language_code)
            .order_by(Dataset.created_at, Dataset.id)
        ).all()
        for dataset in datasets:
            if dataset.id not in seen_ids:
                selected.append(dataset)
                seen_ids.add(dataset.id)

    if selected:
        return selected

    datasets_with_translation_rows = session.exec(
        select(Dataset)
        .join(DataRow, DataRow.dataset_id == Dataset.id)
        .join(Label, Label.data_row_id == DataRow.id)
        .where(Label.type == LabelType.translation)
        .order_by(Dataset.created_at, Dataset.id)
        .distinct()
    ).all()
    return list(datasets_with_translation_rows)


def _translation_rows_for_dataset(session: Session, dataset_id: str) -> list[DataRow]:
    rows = session.exec(
        select(DataRow)
        .join(Label, Label.data_row_id == DataRow.id)
        .where(DataRow.dataset_id == dataset_id)
        .where(Label.type == LabelType.translation)
        .where(DataRow.text_content.is_not(None))
        .order_by(DataRow.created_at, DataRow.row_index, DataRow.id)
    ).all()
    deduped: list[DataRow] = []
    seen_ids: set[str] = set()
    for row in rows:
        if row.id in seen_ids or not str(row.text_content or "").strip():
            continue
        deduped.append(row)
        seen_ids.add(row.id)
    return deduped


def _existing_pos_seed_source_ids(session: Session, dataset_id: str) -> set[str]:
    source_ids: set[str] = set()
    rows = session.exec(select(DataRow).where(DataRow.dataset_id == dataset_id)).all()
    for row in rows:
        metadata = row.row_metadata if isinstance(row.row_metadata, dict) else {}
        pos_seed = metadata.get("pos_seed") if isinstance(metadata, dict) else None
        if isinstance(pos_seed, dict) and pos_seed.get("source") == "translation_rows":
            source_id = str(pos_seed.get("source_data_row_id") or "")
            if source_id:
                source_ids.add(source_id)
    return source_ids


def _next_row_index(session: Session, dataset_id: str) -> int:
    rows = session.exec(select(DataRow).where(DataRow.dataset_id == dataset_id)).all()
    if not rows:
        return 0
    return max(row.row_index for row in rows) + 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Create unlabeled POS candidate rows from translation rows.")
    parser.add_argument("--dataset-id", action="append", dest="dataset_ids")
    parser.add_argument("--language-code", action="append", dest="language_codes")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        with Session(engine) as session:
            summaries = create_pos_rows_from_translation(
                session,
                dataset_ids=args.dataset_ids,
                language_codes=args.language_codes,
                limit=args.limit,
                dry_run=args.dry_run,
            )
    except ValueError as exc:
        print(f"[pos-seed] error {exc}", flush=True)
        return 1

    mode = "dry-run" if args.dry_run else "applied"
    if not summaries:
        print("[pos-seed] no datasets with translation rows found", flush=True)
        return 0

    for summary in summaries:
        print(
            "[pos-seed] "
            f"mode={mode} dataset_id={summary.dataset_id} dataset_name={summary.dataset_name!r} "
            f"language_code={summary.language_code} translation_rows_found={summary.translation_rows_found} "
            f"rows_created={summary.rows_created} duplicates_skipped={summary.duplicates_skipped} "
            f"limit={summary.limit}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
