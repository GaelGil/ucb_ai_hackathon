from sqlmodel import select

from app.api.labels.service import LabelsService
from app.database.models import AiSuggestion, DataRow, Dataset, ImportRecord, Label, Language
from app.database.models.data_row import DataSourceType
from app.database.models.label import LabelSource, LabelType
from app.database.models.suggestion import SuggestionStatus as DbSuggestionStatus
from app.schemas import SuggestionReview, SuggestionStatus
from scripts.create_pos_rows_from_translation import create_pos_rows_from_translation


def _create_translation_dataset(
    session,
    *,
    language_code: str = "nah",
    language_name: str = "Nahuatl",
    source_language_code: str = "es",
    source_text_prefix: str = "source sentence",
    translation_text_prefix: str = "translation",
    count: int = 4,
) -> str:
    language = Language(code=language_code, name=language_name)
    dataset = Dataset(language_id=language.id, name=f"{language_name} demo")
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
            text_content=f"{source_text_prefix} {index}",
            row_metadata={
                "csv": {
                    "text": f"{source_text_prefix} {index}",
                    "translation": f"{translation_text_prefix} {index}",
                }
            },
        )
        label = Label(
            dataset_id=dataset.id,
            data_row_id=row.id,
            import_id=import_record.id,
            type=LabelType.translation,
            name="translation",
            value={"text": f"{translation_text_prefix} {index}", "src": source_language_code, "target": language_code},
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
    assert [row.text_content for row in seed_rows] == ["translation 0", "translation 1", "translation 2"]
    assert all(row.row_metadata["csv"]["tags"] == "" for row in seed_rows)
    assert all(row.row_metadata["csv"]["text"] == row.text_content for row in seed_rows)
    assert all(row.row_metadata["pos_seed"]["text_language"] == "nah" for row in seed_rows)
    assert all(row.row_metadata["pos_seed"]["text_source"] == "translation_label" for row in seed_rows)

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


def test_pos_annotation_rows_include_seeded_rows_before_suggestions(session) -> None:
    dataset_id = _create_translation_dataset(session, count=3)
    create_pos_rows_from_translation(session, dataset_ids=[dataset_id], limit=2)
    service = object.__new__(LabelsService)
    service.session = session

    rows, total = service.list_annotation_rows(dataset_id, "pos", limit=10, offset=0)

    assert total == 2
    assert [row.text for row in rows] == ["translation 0", "translation 1"]
    assert all(row.pending_suggestion is None for row in rows)


def test_pos_annotation_rows_can_filter_to_pending_review_rows(session) -> None:
    dataset_id = _create_translation_dataset(session, count=3)
    create_pos_rows_from_translation(session, dataset_ids=[dataset_id], limit=2)
    seed_row = _pos_seed_rows(session, dataset_id)[0]
    suggestion = AiSuggestion(
        dataset_id=dataset_id,
        data_row_id=seed_row.id,
        label_type=LabelType.pos,
        status=DbSuggestionStatus.pending,
        original_value={
            "text": seed_row.text_content,
            "tokens": [
                {
                    "index": 0,
                    "token": "source",
                    "suggested_pos": "NOUN",
                    "confidence": 0.8,
                    "rationale": "Test token.",
                }
            ],
        },
        confidence=0.8,
        rationale="Pending POS suggestion.",
    )
    session.add(suggestion)
    session.commit()
    service = object.__new__(LabelsService)
    service.session = session

    rows, total = service.list_annotation_rows(dataset_id, "pos", limit=10, offset=0, needs_review=True)

    assert total == 1
    assert len(rows) == 1
    assert rows[0].data_row_id == seed_row.id
    assert rows[0].pending_suggestion is not None
    assert rows[0].pending_suggestion.id == suggestion.id


def test_pos_annotation_rows_include_saved_label_after_acceptance(session) -> None:
    dataset_id = _create_translation_dataset(session, count=3)
    create_pos_rows_from_translation(session, dataset_ids=[dataset_id], limit=2)
    seed_row = _pos_seed_rows(session, dataset_id)[0]
    suggestion = AiSuggestion(
        dataset_id=dataset_id,
        data_row_id=seed_row.id,
        label_type=LabelType.pos,
        status=DbSuggestionStatus.pending,
        original_value={
            "text": seed_row.text_content,
            "tokens": [
                {
                    "index": 0,
                    "token": "translation",
                    "suggested_pos": "NOUN",
                    "confidence": 0.8,
                    "rationale": "Test token.",
                }
            ],
        },
        confidence=0.8,
        rationale="Pending POS suggestion.",
    )
    session.add(suggestion)
    session.commit()
    service = object.__new__(LabelsService)
    service.session = session

    service.review_suggestion(suggestion.id, SuggestionReview(action=SuggestionStatus.ACCEPTED))
    rows, total = service.list_annotation_rows(dataset_id, "pos", limit=10, offset=0)
    review_rows, review_total = service.list_annotation_rows(dataset_id, "pos", limit=10, offset=0, needs_review=True)

    assert total == 2
    reviewed_row = next(row for row in rows if row.data_row_id == seed_row.id)
    assert reviewed_row.pending_suggestion is None
    assert reviewed_row.label is not None
    assert reviewed_row.label.source == LabelSource.ai_accepted.value
    assert reviewed_row.label.value["tokens"][0]["suggested_pos"] == "NOUN"
    assert review_total == 0
    assert review_rows == []


def test_create_pos_rows_from_translation_uses_gaelic_target_text(session) -> None:
    dataset_id = _create_translation_dataset(
        session,
        language_code="glc",
        language_name="Gaelic",
        source_language_code="en",
        source_text_prefix="english sentence",
        translation_text_prefix="gaelic sentence",
        count=2,
    )

    summaries = create_pos_rows_from_translation(session, dataset_ids=[dataset_id], limit=2)

    assert summaries[0].language_code == "glc"
    assert summaries[0].rows_created == 2
    seed_rows = _pos_seed_rows(session, dataset_id)
    assert [row.text_content for row in seed_rows] == ["gaelic sentence 0", "gaelic sentence 1"]
    assert all("english sentence" not in str(row.text_content) for row in seed_rows)


def test_create_pos_rows_from_translation_can_reset_bad_source_language_rows(session) -> None:
    dataset_id = _create_translation_dataset(session, count=2)
    create_pos_rows_from_translation(session, dataset_ids=[dataset_id], limit=2)
    original_seed_rows = _pos_seed_rows(session, dataset_id)

    for index, seed_row in enumerate(original_seed_rows):
        metadata = dict(seed_row.row_metadata)
        csv_metadata = dict(metadata["csv"])
        csv_metadata["text"] = f"source sentence {index}"
        metadata["csv"] = csv_metadata
        seed_row.text_content = f"source sentence {index}"
        seed_row.row_metadata = metadata
        session.add(seed_row)

    stale_suggestion = AiSuggestion(
        dataset_id=dataset_id,
        data_row_id=original_seed_rows[0].id,
        label_type=LabelType.pos,
        status=DbSuggestionStatus.pending,
        original_value={"text": original_seed_rows[0].text_content, "tokens": []},
        confidence=0.4,
        rationale="Stale Spanish suggestion.",
    )
    session.add(stale_suggestion)
    session.commit()

    summaries = create_pos_rows_from_translation(
        session,
        dataset_ids=[dataset_id],
        limit=2,
        reset_existing=True,
    )

    assert summaries[0].seed_rows_deleted == 2
    assert summaries[0].suggestions_deleted == 1
    assert summaries[0].rows_created == 2
    assert session.get(AiSuggestion, stale_suggestion.id) is None
    new_seed_rows = _pos_seed_rows(session, dataset_id)
    assert {row.id for row in new_seed_rows}.isdisjoint({row.id for row in original_seed_rows})
    assert [row.text_content for row in new_seed_rows] == ["translation 0", "translation 1"]
