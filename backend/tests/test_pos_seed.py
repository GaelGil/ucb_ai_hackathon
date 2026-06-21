from sqlmodel import select

from app.api.labels.service import LabelsService
from app.database.models import DataRow, Dataset, ImportRecord, Label, Language
from app.database.models.data import DataSourceType
from app.database.models.label import LabelSource, LabelType
from scripts.create_pos_rows_from_translation import create_pos_rows_from_translation


def _create_translation_dataset(session, *, language_code: str = "nah", count: int = 4) -> str:
    language = Language(code=language_code, name="Nahuatl")
    dataset = Dataset(language_id=language.id, name="Nahuatl demo")
    import_record = ImportRecord(
        dataset_id=dataset.id,
        source_type=DataSourceType.csv,
        filename=f"{language_code}.csv",
        row_count=count,
        label_count=count,
    )
    session.add(language)
    session.add(dataset)
    session.add(import_record)

    for index in range(count):
        row = DataRow(
            dataset_id=dataset.id,
            import_id=import_record.id,
            row_index=index,
            source_type=DataSourceType.csv,
            text_content=f"source sentence {index}",
            row_metadata={"csv": {"text": f"source sentence {index}", "translation": f"translation {index}"}},
        )
        label = Label(
            dataset_id=dataset.id,
            data_row_id=row.id,
            import_id=import_record.id,
            type=LabelType.translation,
            name="translation",
            value={"text": f"translation {index}", "src": "es", "target": language_code},
            source=LabelSource.csv_import,
            original_column_name="translation",
        )
        session.add(row)
        session.add(label)
    session.commit()
    return dataset.id


def _pos_seed_rows(session, dataset_id: str) -> list[DataRow]:
    rows = session.exec(select(DataRow).where(DataRow.dataset_id == dataset_id)).all()
    return [
        row
        for row in rows
        if isinstance(row.row_metadata, dict)
        and isinstance(row.row_metadata.get("pos_seed"), dict)
        and row.row_metadata["pos_seed"].get("source") == "translation_rows"
    ]


def test_create_pos_rows_from_translation_creates_unlabeled_seed_rows(session) -> None:
    dataset_id = _create_translation_dataset(session, count=4)

    summaries = create_pos_rows_from_translation(session, dataset_ids=[dataset_id], limit=3)

    assert len(summaries) == 1
    assert summaries[0].translation_rows_found == 3
    assert summaries[0].rows_created == 3
    seed_rows = _pos_seed_rows(session, dataset_id)
    assert len(seed_rows) == 3
    assert [row.text_content for row in seed_rows] == ["source sentence 0", "source sentence 1", "source sentence 2"]
    assert all(row.row_metadata["csv"]["tags"] == "" for row in seed_rows)

    pos_labels = session.exec(
        select(Label).where(Label.dataset_id == dataset_id).where(Label.type == LabelType.pos)
    ).all()
    assert pos_labels == []

    seed_imports = session.exec(
        select(ImportRecord)
        .where(ImportRecord.dataset_id == dataset_id)
        .where(ImportRecord.filename == "pos-seed-from-translation-nah.csv")
    ).all()
    assert len(seed_imports) == 1
    assert seed_imports[0].row_count == 3
    assert seed_imports[0].label_count == 0


def test_create_pos_rows_from_translation_is_idempotent(session) -> None:
    dataset_id = _create_translation_dataset(session, count=3)

    create_pos_rows_from_translation(session, dataset_ids=[dataset_id], limit=3)
    summaries = create_pos_rows_from_translation(session, dataset_ids=[dataset_id], limit=3)

    assert summaries[0].rows_created == 0
    assert summaries[0].duplicates_skipped == 3
    assert len(_pos_seed_rows(session, dataset_id)) == 3


def test_pos_seed_rows_are_used_for_pos_candidates_not_translation_candidates(session) -> None:
    dataset_id = _create_translation_dataset(session, count=3)
    create_pos_rows_from_translation(session, dataset_ids=[dataset_id], limit=2)
    service = object.__new__(LabelsService)
    service.session = session

    pos_candidates = service._candidate_text_rows(dataset_id, LabelType.pos, limit=10)
    translation_candidates = service._candidate_text_rows(dataset_id, LabelType.translation, limit=10)

    assert len(pos_candidates) == 2
    assert all(service._is_pos_seed_row(row) for row in pos_candidates)
    assert translation_candidates == []
