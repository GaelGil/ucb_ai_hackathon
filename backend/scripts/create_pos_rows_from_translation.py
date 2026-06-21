from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.src.database.models  # noqa: F401  (registers SQLModel tables)
from app.src.database.models import AiSuggestion, DataRow, Dataset, ImportRecord, Label, Language
from app.src.database.models.data import DataSourceType
from app.src.database.models.label import LabelType
from app.src.database.session import engine


SCRIPT_NAME = "create_pos_rows_from_translation.py"
LANGUAGE_CODE_ALIAS_GROUPS = (
    {"glc", "ga", "gle", "irish"},
)


@dataclass
class TranslationSeedCandidate:
    source_row: DataRow
    translation_label: Label
    text: str
    text_source: str


@dataclass
class PosSeedSummary:
    dataset_id: str
    dataset_name: str
    language_code: str
    translation_rows_found: int
    rows_created: int
    duplicates_skipped: int
    seed_rows_deleted: int
    suggestions_deleted: int
    labels_deleted: int
    limit: int
    dry_run: bool
    reset_existing: bool


def create_pos_rows_from_translation(
    session: Session,
    *,
    dataset_ids: list[str] | None = None,
    language_codes: list[str] | None = None,
    limit: int = 100,
    dry_run: bool = False,
    reset_existing: bool = False,
) -> list[PosSeedSummary]:
    if limit <= 0:
        raise ValueError("limit must be greater than 0")

    datasets = _selected_datasets(session, dataset_ids=dataset_ids, language_codes=language_codes)
    summaries: list[PosSeedSummary] = []

    for dataset in datasets:
        language = session.get(Language, dataset.language_id)
        language_code = language.code if language else "unknown"
        seed_rows_deleted = 0
        suggestions_deleted = 0
        labels_deleted = 0

        if reset_existing:
            seed_rows_deleted, suggestions_deleted, labels_deleted = _delete_existing_pos_seed_rows(
                session,
                dataset.id,
                dry_run=dry_run,
            )

        translation_candidates = _translation_seed_candidates_for_dataset(
            session,
            dataset_id=dataset.id,
            language_code=language_code,
        )[:limit]
        existing_source_ids = set() if reset_existing else _existing_pos_seed_source_ids(session, dataset.id)
        rows_to_create = [
            candidate for candidate in translation_candidates if candidate.source_row.id not in existing_source_ids
        ]
        duplicates_skipped = len(translation_candidates) - len(rows_to_create)

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
            for offset, candidate in enumerate(rows_to_create):
                source_row = candidate.source_row
                metadata = dict(source_row.row_metadata or {})
                seed_row = DataRow(
                    dataset_id=dataset.id,
                    import_id=import_record.id,
                    row_index=next_row_index + offset,
                    source_type=DataSourceType.csv,
                    text_content=candidate.text,
                    row_metadata={
                        "csv": {"text": candidate.text, "tags": ""},
                        "pos_seed": {
                            "source": "translation_rows",
                            "source_data_row_id": source_row.id,
                            "source_import_id": source_row.import_id,
                            "translation_label_id": candidate.translation_label.id,
                            "text_language": language_code,
                            "text_source": candidate.text_source,
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
                translation_rows_found=len(translation_candidates),
                rows_created=len(rows_to_create) if not dry_run else 0,
                duplicates_skipped=duplicates_skipped,
                seed_rows_deleted=seed_rows_deleted,
                suggestions_deleted=suggestions_deleted,
                labels_deleted=labels_deleted,
                limit=limit,
                dry_run=dry_run,
                reset_existing=reset_existing,
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


def _translation_seed_candidates_for_dataset(
    session: Session,
    *,
    dataset_id: str,
    language_code: str,
) -> list[TranslationSeedCandidate]:
    rows = session.exec(
        select(DataRow, Label)
        .join(Label, Label.data_row_id == DataRow.id)
        .where(DataRow.dataset_id == dataset_id)
        .where(Label.type == LabelType.translation)
        .order_by(DataRow.created_at, DataRow.row_index, DataRow.id)
    ).all()
    candidates: list[TranslationSeedCandidate] = []
    seen_ids: set[str] = set()
    for source_row, translation_label in rows:
        if source_row.id in seen_ids:
            continue
        text, text_source = _low_resource_text_for_pos_seed(
            source_row,
            translation_label,
            language_code=language_code,
        )
        if not text:
            continue
        candidates.append(
            TranslationSeedCandidate(
                source_row=source_row,
                translation_label=translation_label,
                text=text,
                text_source=text_source,
            )
        )
        seen_ids.add(source_row.id)
    return candidates


def _low_resource_text_for_pos_seed(
    source_row: DataRow,
    translation_label: Label,
    *,
    language_code: str,
) -> tuple[str, str]:
    value = translation_label.value if isinstance(translation_label.value, dict) else {}
    translation_text = _clean_text(value.get("text")) or _metadata_translation_text(source_row)
    source_text = _clean_text(source_row.text_content)
    source_language = _clean_code(value.get("src"))
    target_language = _clean_code(value.get("target"))
    dataset_language = _clean_code(language_code)

    if _language_codes_match(target_language, dataset_language) and translation_text:
        return translation_text, "translation_label"
    if _language_codes_match(source_language, dataset_language) and source_text:
        return source_text, "source_row"
    return "", ""


def _metadata_translation_text(source_row: DataRow) -> str:
    metadata = source_row.row_metadata if isinstance(source_row.row_metadata, dict) else {}
    csv_metadata = metadata.get("csv") if isinstance(metadata, dict) else None
    if not isinstance(csv_metadata, dict):
        return ""
    return _clean_text(csv_metadata.get("translation"))


def _language_codes_match(value: str, language_code: str) -> bool:
    if value == language_code:
        return True
    for alias_group in LANGUAGE_CODE_ALIAS_GROUPS:
        if language_code in alias_group and value in alias_group:
            return True
    return False


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_code(value: object) -> str:
    return str(value or "").strip().lower()


def _existing_pos_seed_source_ids(session: Session, dataset_id: str) -> set[str]:
    source_ids: set[str] = set()
    for row in _pos_seed_rows_for_dataset(session, dataset_id):
        metadata = row.row_metadata if isinstance(row.row_metadata, dict) else {}
        pos_seed = metadata.get("pos_seed") if isinstance(metadata, dict) else None
        if isinstance(pos_seed, dict) and pos_seed.get("source") == "translation_rows":
            source_id = str(pos_seed.get("source_data_row_id") or "")
            if source_id:
                source_ids.add(source_id)
    return source_ids


def _pos_seed_rows_for_dataset(session: Session, dataset_id: str) -> list[DataRow]:
    rows = session.exec(select(DataRow).where(DataRow.dataset_id == dataset_id)).all()
    seed_rows: list[DataRow] = []
    for row in rows:
        metadata = row.row_metadata if isinstance(row.row_metadata, dict) else {}
        pos_seed = metadata.get("pos_seed") if isinstance(metadata, dict) else None
        if isinstance(pos_seed, dict) and pos_seed.get("source") == "translation_rows":
            seed_rows.append(row)
    return seed_rows


def _delete_existing_pos_seed_rows(
    session: Session,
    dataset_id: str,
    *,
    dry_run: bool,
) -> tuple[int, int, int]:
    seed_rows = _pos_seed_rows_for_dataset(session, dataset_id)
    seed_row_ids = [row.id for row in seed_rows]
    if not seed_row_ids:
        return 0, 0, 0

    suggestions = session.exec(select(AiSuggestion).where(AiSuggestion.data_row_id.in_(seed_row_ids))).all()
    labels = session.exec(select(Label).where(Label.data_row_id.in_(seed_row_ids))).all()

    if not dry_run:
        for suggestion in suggestions:
            session.delete(suggestion)
        for label in labels:
            session.delete(label)
        for row in seed_rows:
            session.delete(row)
        session.flush()

    return len(seed_rows), len(suggestions), len(labels)


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
    parser.add_argument(
        "--reset-existing",
        action="store_true",
        help="Delete existing POS seed rows for selected datasets before reseeding them.",
    )
    args = parser.parse_args()

    try:
        with Session(engine) as session:
            summaries = create_pos_rows_from_translation(
                session,
                dataset_ids=args.dataset_ids,
                language_codes=args.language_codes,
                limit=args.limit,
                dry_run=args.dry_run,
                reset_existing=args.reset_existing,
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
            f"reset_existing={summary.reset_existing} seed_rows_deleted={summary.seed_rows_deleted} "
            f"suggestions_deleted={summary.suggestions_deleted} labels_deleted={summary.labels_deleted} "
            f"limit={summary.limit}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
