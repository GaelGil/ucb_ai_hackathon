from sqlmodel import select

from app.api.labels.service import LabelsService
from app.schemas import SuggestionReview, SuggestionStatus as ApiSuggestionStatus
from app.database.models import AiSuggestion, DataRow, Dataset, ImportRecord, Label, Language
from app.database.models.data import DataSourceType
from app.database.models.label import LabelSource, LabelType
from app.database.models.suggestion import SuggestionStatus
from scripts.blank_translation_labels import enforce_translation_split


def _create_translation_dataset(session, *, language_code: str, language_name: str) -> str:
    language = Language(code=language_code, name=language_name)
    dataset = Dataset(language_id=language.id, name=f"{language_name} translations")
    import_record = ImportRecord(
        dataset_id=dataset.id,
        source_type=DataSourceType.csv,
        row_count=100,
        label_count=100,
        filename=f"{language_code}.csv",
    )
    session.add(language)
    session.add(dataset)
    session.add(import_record)

    for index in range(100):
        translation = f"{language_code} translation {index}"
        row = DataRow(
            dataset_id=dataset.id,
            import_id=import_record.id,
            row_index=index,
            source_type=DataSourceType.csv,
            text_content=f"source sentence {index}",
            row_metadata={"csv": {"translation": translation, "src": "en", "target": language_code}},
        )
        label = Label(
            dataset_id=dataset.id,
            data_row_id=row.id,
            import_id=import_record.id,
            type=LabelType.translation,
            name="translation",
            value={"text": translation, "src": "en", "target": language_code},
            source=LabelSource.csv_import,
            original_column_name="translation",
        )
        session.add(row)
        session.add(label)
    session.commit()
    return dataset.id


def _translation_labels(session, dataset_id: str) -> list[Label]:
    return session.exec(
        select(Label)
        .join(DataRow, Label.data_row_id == DataRow.id)
        .where(Label.dataset_id == dataset_id)
        .where(Label.type == LabelType.translation)
        .order_by(DataRow.row_index)
    ).all()


def _rows(session, dataset_id: str) -> list[DataRow]:
    return session.exec(
        select(DataRow).where(DataRow.dataset_id == dataset_id).order_by(DataRow.row_index)
    ).all()


def test_translation_split_blanks_40_per_language_and_candidates_include_blanks(session) -> None:
    ga_dataset_id = _create_translation_dataset(session, language_code="ga", language_name="Irish")
    nah_dataset_id = _create_translation_dataset(session, language_code="nah", language_name="Nahuatl")

    summaries = enforce_translation_split(session, language_codes=["ga", "nah"])

    assert {summary.language_code: summary.labels_blanked for summary in summaries} == {"ga": 40, "nah": 40}
    for dataset_id in [ga_dataset_id, nah_dataset_id]:
        labels = _translation_labels(session, dataset_id)
        texts = [str(label.value.get("text") or "") for label in labels]
        assert all(texts[:60])
        assert texts[60:] == [""] * 40

        rows = _rows(session, dataset_id)
        assert rows[59].row_metadata["csv"]["translation"]
        assert rows[60].row_metadata["csv"]["translation"] == ""

        service = object.__new__(LabelsService)
        service.session = session
        candidates = service._candidate_text_rows(dataset_id, LabelType.translation, limit=100)
        assert {row.row_index for row in candidates} == set(range(60, 100))


def test_translation_labels_are_interleaved_for_demo_pagination(session) -> None:
    dataset_id = _create_translation_dataset(session, language_code="glc", language_name="Gaelic")
    enforce_translation_split(session, language_codes=["glc"])

    service = object.__new__(LabelsService)
    service.session = session
    first_page, total = service.list_labels(dataset_id, "translation", limit=10, offset=0)

    assert total == 100
    values = [str(label.value.get("text") or "") for label in first_page]
    assert values.count("") == 4
    assert all(value for value in values[:6])
    assert values[6:] == [""] * 4


def test_accepting_translation_suggestion_reuses_blank_label(session) -> None:
    dataset_id = _create_translation_dataset(session, language_code="ga", language_name="Irish")
    enforce_translation_split(session, language_codes=["ga"])

    service = object.__new__(LabelsService)
    service.session = session
    row = service._candidate_text_rows(dataset_id, LabelType.translation, limit=1)[0]
    suggestion = AiSuggestion(
        dataset_id=dataset_id,
        data_row_id=row.id,
        label_type=LabelType.translation,
        status=SuggestionStatus.accepted,
        original_value={"text": "accepted translation"},
    )
    session.add(suggestion)
    session.commit()

    service._upsert_label_for_suggestion(suggestion)
    session.commit()

    labels = session.exec(
        select(Label)
        .where(Label.dataset_id == dataset_id)
        .where(Label.data_row_id == row.id)
        .where(Label.type == LabelType.translation)
    ).all()
    assert len(labels) == 1
    assert labels[0].ai_suggestion_id == suggestion.id
    assert labels[0].value["text"] == "accepted translation"


def test_translation_labels_include_pending_suggestion_for_same_row(session) -> None:
    dataset_id = _create_translation_dataset(session, language_code="ga", language_name="Irish")
    enforce_translation_split(session, language_codes=["ga"])

    service = object.__new__(LabelsService)
    service.session = session
    row = service._candidate_text_rows(dataset_id, LabelType.translation, limit=1)[0]
    suggestion = AiSuggestion(
        dataset_id=dataset_id,
        data_row_id=row.id,
        label_type=LabelType.translation,
        status=SuggestionStatus.pending,
        original_value={"source_text": row.text_content, "text": "pending translation"},
        confidence=0.8,
        rationale="Pending translation suggestion.",
    )
    session.add(suggestion)
    session.commit()

    labels, _ = service.list_labels(dataset_id, "translation", limit=10, offset=0)
    label = next(label for label in labels if label.data_row_id == row.id)

    assert label.pending_suggestion is not None
    assert label.pending_suggestion.id == suggestion.id
    assert label.pending_suggestion.suggested_text == "pending translation"

    service.review_suggestion(
        suggestion.id,
        SuggestionReview(action=ApiSuggestionStatus.ACCEPTED),
    )

    labels, _ = service.list_labels(dataset_id, "translation", limit=10, offset=0)
    label = next(label for label in labels if label.data_row_id == row.id)
    assert label.pending_suggestion is None
    assert label.value["text"] == "pending translation"


def test_translation_labels_can_filter_to_pending_review_rows(session) -> None:
    dataset_id = _create_translation_dataset(session, language_code="ga", language_name="Irish")
    enforce_translation_split(session, language_codes=["ga"])

    service = object.__new__(LabelsService)
    service.session = session
    row = service._candidate_text_rows(dataset_id, LabelType.translation, limit=1)[0]
    suggestion = AiSuggestion(
        dataset_id=dataset_id,
        data_row_id=row.id,
        label_type=LabelType.translation,
        status=SuggestionStatus.pending,
        original_value={"source_text": row.text_content, "text": "pending translation"},
        confidence=0.8,
        rationale="Pending translation suggestion.",
    )
    session.add(suggestion)
    session.commit()

    labels, total = service.list_labels(dataset_id, "translation", limit=10, offset=0, needs_review=True)

    assert total == 1
    assert len(labels) == 1
    assert labels[0].data_row_id == row.id
    assert labels[0].pending_suggestion is not None
