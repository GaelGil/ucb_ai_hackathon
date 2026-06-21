from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.src.database.models  # noqa: F401  (registers SQLModel tables)
from app.src.database.models import DataRow, Dataset, Label, Language
from app.src.database.models.label import LabelType
from app.src.database.models.language import now_utc
from app.src.database.session import engine


@dataclass
class SplitSummary:
    language_code: str
    total_translation_labels: int
    kept_complete_target: int
    blank_target: int
    labels_blanked: int
    labels_already_blank: int
    skipped_after_target: int
    complete_after_target: int
    dry_run: bool


def _translation_pairs_for_language(session: Session, language_code: str) -> list[tuple[Label, DataRow]]:
    return session.exec(
        select(Label, DataRow)
        .join(DataRow, Label.data_row_id == DataRow.id)
        .join(Dataset, DataRow.dataset_id == Dataset.id)
        .join(Language, Dataset.language_id == Language.id)
        .where(Language.code == language_code)
        .where(Label.type == LabelType.translation)
        .order_by(DataRow.created_at, DataRow.row_index, Label.created_at, Label.id)
    ).all()


def _translation_text(label: Label) -> str:
    value = label.value or {}
    return str(value.get("text") or "").strip()


def _blank_translation(label: Label, row: DataRow) -> None:
    value = dict(label.value or {})
    value["text"] = ""
    label.value = value
    label.updated_at = now_utc()

    metadata = dict(row.row_metadata or {})
    csv_metadata = metadata.get("csv")
    if isinstance(csv_metadata, dict):
        updated_csv = dict(csv_metadata)
        updated_csv["translation"] = ""
        metadata["csv"] = updated_csv
        row.row_metadata = metadata
        row.updated_at = now_utc()


def enforce_translation_split(
    session: Session,
    *,
    language_codes: list[str],
    complete_count: int = 60,
    blank_count: int = 40,
    dry_run: bool = False,
) -> list[SplitSummary]:
    summaries: list[SplitSummary] = []
    target_count = complete_count + blank_count

    for language_code in language_codes:
        pairs = _translation_pairs_for_language(session, language_code)
        blank_pairs = pairs[complete_count:target_count]
        labels_blanked = 0
        labels_already_blank = 0

        for label, row in blank_pairs:
            if _translation_text(label):
                labels_blanked += 1
            else:
                labels_already_blank += 1
            if not dry_run:
                _blank_translation(label, row)
                session.add(label)
                session.add(row)

        controlled_pairs = pairs[:target_count]
        complete_after_target = sum(
            1
            for index, (label, _) in enumerate(controlled_pairs)
            if index < complete_count and _translation_text(label)
        )
        summaries.append(
            SplitSummary(
                language_code=language_code,
                total_translation_labels=len(pairs),
                kept_complete_target=complete_count,
                blank_target=blank_count,
                labels_blanked=labels_blanked,
                labels_already_blank=labels_already_blank,
                skipped_after_target=max(0, len(pairs) - target_count),
                complete_after_target=complete_after_target,
                dry_run=dry_run,
            )
        )

    if not dry_run:
        session.commit()

    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description="Blank translation labels to create demo suggestion candidates.")
    parser.add_argument("--language-code", action="append", dest="language_codes")
    parser.add_argument("--complete-count", type=int, default=60)
    parser.add_argument("--blank-count", type=int, default=40)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.complete_count < 0 or args.blank_count < 0:
        print("[blank-translation-labels] error counts must be >= 0", flush=True)
        return 1

    language_codes = args.language_codes or ["ga", "nah"]
    with Session(engine) as session:
        summaries = enforce_translation_split(
            session,
            language_codes=language_codes,
            complete_count=args.complete_count,
            blank_count=args.blank_count,
            dry_run=args.dry_run,
        )

    mode = "dry-run" if args.dry_run else "applied"
    for summary in summaries:
        print(
            "[blank-translation-labels] "
            f"mode={mode} language_code={summary.language_code} "
            f"total_translation_labels={summary.total_translation_labels} "
            f"kept_complete_target={summary.kept_complete_target} "
            f"blank_target={summary.blank_target} labels_blanked={summary.labels_blanked} "
            f"labels_already_blank={summary.labels_already_blank} "
            f"complete_after_target={summary.complete_after_target} "
            f"skipped_after_target={summary.skipped_after_target}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
