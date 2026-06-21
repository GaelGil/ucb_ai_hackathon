# from __future__ import annotations

# import argparse
# import sys
# from dataclasses import dataclass
# from pathlib import Path

# from sqlalchemy import delete, func
# from sqlmodel import Session, select

# sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# import app.src.database.models  # noqa: F401  (registers SQLModel tables)
# from app.src.database.models import AiSuggestion, DataRow, Dataset, ImportRecord, Label, Language
# from app.src.database.models.language import now_utc
# from app.src.database.session import engine


# DELETE_CHUNK_SIZE = 1000


# @dataclass
# class TrimSummary:
#     language_code: str
#     limit: int
#     datasets: int
#     imports_before: int
#     rows_before: int
#     labels_before: int
#     suggestions_before: int
#     rows_kept: int
#     rows_deleted: int
#     labels_deleted: int
#     suggestions_deleted: int
#     imports_deleted: int
#     imports_updated: int
#     dry_run: bool


# def _chunks(values: list[str], size: int = DELETE_CHUNK_SIZE):
#     for index in range(0, len(values), size):
#         yield values[index : index + size]


# def _count_for_ids(session: Session, model, column, ids: list[str]) -> int:
#     if not ids:
#         return 0
#     total = 0
#     for chunk in _chunks(ids):
#         total += session.exec(select(func.count()).select_from(model).where(column.in_(chunk))).one()
#     return total


# def _delete_for_ids(session: Session, model, column, ids: list[str]) -> None:
#     for chunk in _chunks(ids):
#         session.exec(delete(model).where(column.in_(chunk)))


# def _timestamp(value) -> float:
#     return value.timestamp() if value is not None else 0.0


# def trim_language_rows(session: Session, *, language_code: str, limit: int, dry_run: bool) -> TrimSummary:
#     language = session.exec(select(Language).where(Language.code == language_code)).first()
#     if language is None:
#         return TrimSummary(
#             language_code=language_code,
#             limit=limit,
#             datasets=0,
#             imports_before=0,
#             rows_before=0,
#             labels_before=0,
#             suggestions_before=0,
#             rows_kept=0,
#             rows_deleted=0,
#             labels_deleted=0,
#             suggestions_deleted=0,
#             imports_deleted=0,
#             imports_updated=0,
#             dry_run=dry_run,
#         )

#     datasets = session.exec(select(Dataset).where(Dataset.language_id == language.id)).all()
#     dataset_ids = [dataset.id for dataset in datasets]
#     if not dataset_ids:
#         return TrimSummary(
#             language_code=language_code,
#             limit=limit,
#             datasets=0,
#             imports_before=0,
#             rows_before=0,
#             labels_before=0,
#             suggestions_before=0,
#             rows_kept=0,
#             rows_deleted=0,
#             labels_deleted=0,
#             suggestions_deleted=0,
#             imports_deleted=0,
#             imports_updated=0,
#             dry_run=dry_run,
#         )

#     imports = session.exec(select(ImportRecord).where(ImportRecord.dataset_id.in_(dataset_ids))).all()
#     import_by_id = {record.id: record for record in imports}

#     rows = session.exec(
#         select(
#             DataRow.id,
#             DataRow.import_id,
#             DataRow.row_index,
#             DataRow.created_at,
#         ).where(DataRow.dataset_id.in_(dataset_ids))
#     ).all()
#     labels_before = _count_for_ids(session, Label, Label.dataset_id, dataset_ids)
#     suggestions_before = _count_for_ids(session, AiSuggestion, AiSuggestion.dataset_id, dataset_ids)

#     def keep_order(row) -> tuple[float, int, float, str]:
#         row_id, import_id, row_index, created_at = row
#         record = import_by_id.get(import_id or "")
#         import_created_at = record.created_at if record is not None else created_at
#         return (-_timestamp(import_created_at), row_index or 0, _timestamp(created_at), row_id)

#     rows_to_keep = sorted(rows, key=keep_order)[:limit]
#     keep_ids = {row[0] for row in rows_to_keep}
#     delete_row_ids = [row[0] for row in rows if row[0] not in keep_ids]

#     labels_deleted = _count_for_ids(session, Label, Label.data_row_id, delete_row_ids)
#     suggestions_deleted = _count_for_ids(session, AiSuggestion, AiSuggestion.data_row_id, delete_row_ids)

#     imports_deleted = 0
#     imports_updated = 0
#     if not dry_run and delete_row_ids:
#         _delete_for_ids(session, Label, Label.data_row_id, delete_row_ids)
#         _delete_for_ids(session, AiSuggestion, AiSuggestion.data_row_id, delete_row_ids)
#         _delete_for_ids(session, DataRow, DataRow.id, delete_row_ids)
#         session.flush()

#         for record in imports:
#             row_count = session.exec(
#                 select(func.count()).select_from(DataRow).where(DataRow.import_id == record.id)
#             ).one()
#             label_count = session.exec(
#                 select(func.count()).select_from(Label).where(Label.import_id == record.id)
#             ).one()
#             if row_count == 0 and label_count == 0:
#                 session.delete(record)
#                 imports_deleted += 1
#                 continue
#             if record.row_count != row_count or record.label_count != label_count:
#                 record.row_count = row_count
#                 record.label_count = label_count
#                 record.updated_at = now_utc()
#                 session.add(record)
#                 imports_updated += 1

#         session.commit()
#     elif not dry_run:
#         session.commit()

#     return TrimSummary(
#         language_code=language_code,
#         limit=limit,
#         datasets=len(datasets),
#         imports_before=len(imports),
#         rows_before=len(rows),
#         labels_before=labels_before,
#         suggestions_before=suggestions_before,
#         rows_kept=len(rows_to_keep),
#         rows_deleted=len(delete_row_ids),
#         labels_deleted=labels_deleted,
#         suggestions_deleted=suggestions_deleted,
#         imports_deleted=imports_deleted,
#         imports_updated=imports_updated,
#         dry_run=dry_run,
#     )


# def main() -> int:
#     parser = argparse.ArgumentParser(description="Trim language data rows to a fixed demo size.")
#     parser.add_argument("--language-code", default="nah")
#     parser.add_argument("--limit", type=int, default=100)
#     parser.add_argument("--dry-run", action="store_true")
#     args = parser.parse_args()

#     if args.limit < 0:
#         print("[trim-language-rows] error limit must be >= 0", flush=True)
#         return 1

#     with Session(engine) as session:
#         summary = trim_language_rows(
#             session,
#             language_code=args.language_code,
#             limit=args.limit,
#             dry_run=args.dry_run,
#         )

#     mode = "dry-run" if summary.dry_run else "applied"
#     print(
#         "[trim-language-rows] "
#         f"mode={mode} language_code={summary.language_code} limit={summary.limit} "
#         f"datasets={summary.datasets} imports_before={summary.imports_before} "
#         f"rows_before={summary.rows_before} rows_kept={summary.rows_kept} "
#         f"rows_deleted={summary.rows_deleted} labels_deleted={summary.labels_deleted} "
#         f"suggestions_deleted={summary.suggestions_deleted} imports_updated={summary.imports_updated} "
#         f"imports_deleted={summary.imports_deleted} labels_before={summary.labels_before} "
#         f"suggestions_before={summary.suggestions_before}",
#         flush=True,
#     )
#     return 0


# if __name__ == "__main__":
#     raise SystemExit(main())
