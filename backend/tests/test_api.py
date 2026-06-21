from dataclasses import replace
import io

import pytest
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from app import create_app
from app.routes.container import SERVICES_CONFIG_KEY
from app.config import Settings
from app.schemas import ResearchArtifact, ResearchSource, TokenSuggestion, TranslationProviderResult


class FakeResearchProvider:
    provider = "fake-browserbase"
    model_name = "fake-claude"

    def create_research(self, dataset, samples, research_type="pos"):
        return ResearchArtifact(
            dataset_id=dataset.id,
            language_code=dataset.language_code,
            type=research_type,
            summary=f"{dataset.language_name} {research_type} notes",
            guidelines=["Use reviewer examples first."],
            sources=[ResearchSource(title="Fake source", url="https://example.test", excerpt="Fake excerpt")],
            metadata={
                "provider": self.provider,
                "model": self.model_name,
                "evaluation": {"score": 0.9, "feedback": "Useful for tests."},
            },
        )


class FakePosProvider:
    provider = "fake-anthropic"
    model_name = "fake-claude"

    def suggest(self, text, research=None):
        tokens = text.split()
        return [
            TokenSuggestion(
                index=index,
                token=token,
                suggested_pos="NOUN",
                confidence=0.8,
                rationale="Fake POS suggestion.",
            )
            for index, token in enumerate(tokens)
        ]


class FakeTranslationProvider:
    provider = "fake-anthropic"
    model_name = "fake-claude"

    def suggest(self, *, text, direction, research, row_metadata=None):
        return TranslationProviderResult(
            output_text=f"translated: {text}",
            provider=self.provider,
            model=self.model_name,
            confidence=0.8,
            rationale="Fake translation suggestion.",
            metadata={"evaluation": {"score": 0.8, "feedback": "Preserves meaning enough for tests."}},
        )

    def translate(self, text, direction="spanish_to_nahuatl"):
        return TranslationProviderResult(
            output_text="miak xochitl istak" if text == "muchas flores son blancas" else f"translated: {text}",
            provider="local-demo",
            model="fake-demo",
            confidence=0.35,
            rationale="Fake demo fallback.",
            used_fallback=True,
            warning={"provider": "aws-neuron-endpoint", "stage": "translation", "message": "Fake warning", "fallback": True},
        )


class FakeOcrProvider:
    provider = "fake-anthropic"
    model_name = "fake-claude"

    def extract(self, asset):
        return "fake extracted text", 0.8, "Fake OCR suggestion."


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        seed_demo_data=True,
        agent_jobs_background=False,
        arize_enabled=False,
        phoenix_enabled=False,
    )
    app = create_app(settings=settings, engine=engine, create_tables=True)
    app.config[SERVICES_CONFIG_KEY] = replace(
        app.config[SERVICES_CONFIG_KEY],
        research_provider=FakeResearchProvider(),
        pos_provider=FakePosProvider(),
        translation_provider=FakeTranslationProvider(),
        ocr_provider=FakeOcrProvider(),
    )
    return app.test_client()


def test_text_pos_research_review_and_training_flow(client) -> None:
    dataset = client.post(
        "/datasets",
        json={"name": "Mixtec pilot", "language_code": "mix", "language_name": "Mixtec"},
    ).get_json()

    imported = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={"text": "la casa grande\nel agua corre rapido", "source_type": "text"},
    ).get_json()
    assert imported["import_record"]["item_count"] == 2

    research = client.post(f"/datasets/{dataset['id']}/research").get_json()
    assert research["research"]["id"].startswith("research_")

    suggestions = client.post(f"/datasets/{dataset['id']}/pos-suggestions", json={"limit": 5}).get_json()["suggestions"]
    assert len(suggestions) == 2
    assert suggestions[0]["research_id"] == research["research"]["id"]
    assert suggestions[0]["tokens"]

    reviewed = client.patch(f"/suggestions/{suggestions[0]['id']}", json={"action": "accepted"}).get_json()
    assert reviewed["status"] == "accepted"

    labels = client.get(f"/datasets/{dataset['id']}/labels", query_string={"type": "pos"}).get_json()["labels"]
    assert len(labels) == 1
    assert labels[0]["source"] == "ai_accepted"

    trained = client.post(
        f"/datasets/{dataset['id']}/pos-model/train",
        json={"minimum_examples": 20, "demo_override": True},
    ).get_json()
    assert trained["pos_model"]["status"] == "ready"
    assert trained["pos_model"]["mode"] == "demo"
    assert trained["pos_model"]["minimum_examples_met"] is False
    assert trained["pos_model"]["accepted_sentence_count"] == 1


def test_research_is_cached_per_dataset_language(client) -> None:
    dataset = client.get("/datasets").get_json()[0]

    first = client.post(f"/datasets/{dataset['id']}/research").get_json()
    second = client.post(f"/datasets/{dataset['id']}/research").get_json()

    assert first["research"]["id"] == second["research"]["id"]
    assert second["job"]["metadata"]["cached"] is True


def test_research_provider_metadata_is_visible(client) -> None:
    dataset = client.get("/datasets").get_json()[0]

    response = client.post(f"/datasets/{dataset['id']}/research").get_json()

    assert response["job"]["metadata"]["provider"] == "fake-browserbase"
    assert response["job"]["metadata"]["model"] == "fake-claude"
    assert response["research"]["metadata"]["evaluation"]["score"] == 0.9
    assert response["research"]["warnings"] == []


def test_research_is_separate_by_type(client) -> None:
    dataset = client.get("/datasets").get_json()[0]

    pos = client.post(f"/datasets/{dataset['id']}/research", query_string={"type": "pos"}).get_json()
    translation = client.post(f"/datasets/{dataset['id']}/research", query_string={"type": "translation"}).get_json()

    assert pos["research"]["id"] != translation["research"]["id"]
    assert pos["research"]["type"] == "pos"
    assert translation["research"]["type"] == "translation"
    assert translation["job"]["metadata"]["research_type"] == "translation"


def test_missing_research_returns_null(client) -> None:
    dataset = client.post(
        "/datasets",
        json={"name": "No research yet", "language_code": "none", "language_name": "None"},
    ).get_json()

    response = client.get(f"/datasets/{dataset['id']}/research", query_string={"type": "translation"})

    assert response.status_code == 200
    assert response.get_json() is None


def test_pos_suggestions_require_pos_research(client) -> None:
    dataset = client.post(
        "/datasets",
        json={"name": "Research gate", "language_code": "gate", "language_name": "Gate"},
    ).get_json()
    client.post(
        f"/datasets/{dataset['id']}/imports",
        json={"text": "uno dos tres", "source_type": "text"},
    )

    response = client.post(f"/datasets/{dataset['id']}/pos-suggestions", json={"limit": 5}).get_json()

    assert response["suggestions"] == []
    assert response["job"]["status"] == "failed"
    assert "POS research must be generated" in response["job"]["error"]


def test_denied_pos_suggestion_can_be_regenerated(client) -> None:
    dataset = client.post(
        "/datasets",
        json={"name": "Regenerate denied", "language_code": "regen", "language_name": "Regenerate"},
    ).get_json()
    client.post(
        f"/datasets/{dataset['id']}/imports",
        json={"text": "uno dos tres", "source_type": "text"},
    )
    client.post(f"/datasets/{dataset['id']}/research").get_json()
    first = client.post(f"/datasets/{dataset['id']}/pos-suggestions", json={"limit": 5}).get_json()["suggestions"]
    client.patch(f"/suggestions/{first[0]['id']}", json={"action": "denied"})

    second = client.post(f"/datasets/{dataset['id']}/pos-suggestions", json={"limit": 5}).get_json()["suggestions"]

    assert len(second) == 1
    assert second[0]["original_text"] == "uno dos tres"
    assert second[0]["id"] != first[0]["id"]


def test_translation_suggestions_require_translation_research(client) -> None:
    dataset = client.post(
        "/datasets",
        json={"name": "No translation research", "language_code": "nah", "language_name": "Nahuatl"},
    ).get_json()
    client.post(
        f"/datasets/{dataset['id']}/imports",
        json={"text": "muchas flores son blancas", "source_type": "text"},
    )

    response = client.post(f"/datasets/{dataset['id']}/translation-suggestions", json={"limit": 5}).get_json()

    assert response["suggestions"] == []
    assert response["job"]["status"] == "failed"
    assert "Translation research must be generated" in response["job"]["error"]


def test_translation_suggestions_skip_existing_translation_labels_and_can_be_reviewed(client) -> None:
    dataset = client.post(
        "/datasets",
        json={"name": "Translation pilot", "language_code": "nah", "language_name": "Nahuatl"},
    ).get_json()
    client.post(
        f"/datasets/{dataset['id']}/imports",
        json={
            "source_type": "csv",
            "import_kind": "translation",
            "text": "text,translation,source,src,target\nmuchas flores son blancas,miak xochitl istak,seed,sp,nah\n",
        },
    )
    client.post(
        f"/datasets/{dataset['id']}/imports",
        json={"text": "el agua corre rapido\nmi familia habla nahuatl", "source_type": "text"},
    )
    research = client.post(f"/datasets/{dataset['id']}/research", query_string={"type": "translation"}).get_json()

    response = client.post(f"/datasets/{dataset['id']}/translation-suggestions", json={"limit": 5}).get_json()

    assert response["job"]["status"] == "succeeded"
    assert response["job"]["metadata"]["research_type"] == "translation"
    assert len(response["suggestions"]) == 2
    assert {suggestion["original_text"] for suggestion in response["suggestions"]} == {
        "el agua corre rapido",
        "mi familia habla nahuatl",
    }
    assert all(suggestion["research_id"] == research["research"]["id"] for suggestion in response["suggestions"])
    assert all(suggestion["suggested_text"] for suggestion in response["suggestions"])

    accepted = client.patch(f"/suggestions/{response['suggestions'][0]['id']}", json={"action": "accepted"}).get_json()
    updated = client.patch(
        f"/suggestions/{response['suggestions'][1]['id']}",
        json={"action": "updated", "edited_text": "nochanehua tlahtoa nahuatlahtolli"},
    ).get_json()

    assert accepted["status"] == "accepted"
    assert updated["status"] == "updated"
    labels = client.get(f"/datasets/{dataset['id']}/labels", query_string={"type": "translation"}).get_json()["labels"]
    values = [label["value"]["text"] for label in labels]
    assert "miak xochitl istak" in values
    assert "nochanehua tlahtoa nahuatlahtolli" in values


def test_ocr_uses_selected_image_import(client) -> None:
    dataset = client.post(
        "/datasets",
        json={"name": "OCR pilot", "language_code": "ocr", "language_name": "OCR"},
    ).get_json()
    uploaded = client.post(
        f"/datasets/{dataset['id']}/imports",
        data={"file": (io.BytesIO(b"fake image bytes"), "note.png", "image/png")},
        content_type="multipart/form-data",
    ).get_json()

    response = client.post(
        f"/datasets/{dataset['id']}/ocr",
        json={"import_ids": [uploaded["import_record"]["id"]]},
    ).get_json()

    assert response["job"]["status"] == "succeeded"
    assert response["job"]["metadata"]["provider"] == "fake-anthropic"
    assert len(response["suggestions"]) == 1
    assert response["suggestions"][0]["suggested_text"] == "fake extracted text"


def test_csv_import_uses_text_column(client) -> None:
    dataset = client.get("/datasets").get_json()[0]

    response = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={"source_type": "csv", "text": "id,text\n1,hello world\n2,second row\n"},
    ).get_json()

    assert response["import_record"]["item_count"] == 2
    assert response["import_record"]["label_count"] == 0
    assert [item["text"] for item in response["created_items"]] == ["hello world", "second row"]


def test_csv_import_can_create_labels(client) -> None:
    dataset = client.get("/datasets").get_json()[0]

    response = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={
            "source_type": "csv",
            "text": "id,text,translation,emotion\n1,hello world,tlasohkamati,happy\n2,second row,ome,neutral\n",
        },
    ).get_json()

    assert response["import_record"]["item_count"] == 2
    assert response["import_record"]["label_count"] == 4
    assert {label["source"] for label in response["created_labels"]} == {"csv_import"}

    translations = client.get(f"/datasets/{dataset['id']}/labels", query_string={"type": "translation"}).get_json()["labels"]
    assert [label["value"]["text"] for label in translations] == ["tlasohkamati", "ome"]
    assert [label["data_text"] for label in translations] == ["hello world", "second row"]


def test_labels_endpoint_paginates(client) -> None:
    dataset = client.get("/datasets").get_json()[0]
    rows = "\n".join(f"{index},source {index},target {index}" for index in range(25))

    client.post(
        f"/datasets/{dataset['id']}/imports",
        json={
            "source_type": "csv",
            "text": f"id,text,translation\n{rows}\n",
        },
    )

    first = client.get(
        f"/datasets/{dataset['id']}/labels",
        query_string={"type": "translation", "limit": 10, "offset": 0},
    ).get_json()
    second = client.get(
        f"/datasets/{dataset['id']}/labels",
        query_string={"type": "translation", "limit": 10, "offset": 10},
    ).get_json()

    assert first["total"] == 25
    assert first["limit"] == 10
    assert first["offset"] == 0
    assert len(first["labels"]) == 10
    assert second["total"] == 25
    assert second["limit"] == 10
    assert second["offset"] == 10
    assert len(second["labels"]) == 10
    assert {label["id"] for label in first["labels"]}.isdisjoint({label["id"] for label in second["labels"]})


def test_translation_csv_import_uses_required_columns(client) -> None:
    dataset = client.get("/datasets").get_json()[0]

    response = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={
            "source_type": "csv",
            "import_kind": "translation",
            "text": (
                "text,translation,source,src,target,source_id_or_reference\n"
                "hello world,tlasohkamati,axolotl,es,nah,1\n"
                "missing translation,,axolotl,es,nah,2\n"
            ),
        },
    ).get_json()

    assert response["job"]["status"] == "succeeded"
    assert response["job"]["metadata"]["import_kind"] == "translation"
    assert response["job"]["metadata"]["skipped_count"] == 1
    assert response["import_record"]["item_count"] == 1
    assert response["import_record"]["label_count"] == 1
    assert response["created_items"][0]["text"] == "hello world"
    assert response["created_labels"][0]["type"] == "translation"
    assert response["created_labels"][0]["name"] == "translation"
    assert response["created_labels"][0]["value"] == {
        "text": "tlasohkamati",
        "source": "axolotl",
        "src": "es",
        "target": "nah",
    }


def test_multipart_translation_csv_import_completes_synchronously(client) -> None:
    dataset = client.get("/datasets").get_json()[0]
    csv_text = (
        "text,translation,source,src,target,source_id_or_reference\n"
        "hello world,tlasohkamati,axolotl,es,nah,1\n"
        "second row,ome,axolotl,es,nah,2\n"
    )

    response = client.post(
        f"/datasets/{dataset['id']}/imports",
        data={
            "import_kind": "translation",
            "file": (io.BytesIO(csv_text.encode()), "sample.csv", "text/csv"),
        },
        content_type="multipart/form-data",
    ).get_json()

    assert response["job"]["status"] == "succeeded"
    assert response["import_record"]["item_count"] == 2
    assert response["import_record"]["label_count"] == 2


def test_pos_csv_import_accepts_text_tags_and_json_list_tags(client) -> None:
    dataset = client.get("/datasets").get_json()[0]

    response = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={
            "source_type": "csv",
            "import_kind": "pos",
            "text": (
                "text,tags\n"
                "\"mi casa\",\"PRON NOUN\"\n"
                "\"el agua\",\"[\"\"DET\"\", \"\"NOUN\"\"]\"\n"
                "\"bad count\",\"NOUN\"\n"
                "\"bad tag\",\"NOUN NOPE\"\n"
            ),
        },
    ).get_json()

    assert response["job"]["status"] == "succeeded"
    assert response["job"]["metadata"]["import_kind"] == "pos"
    assert response["job"]["metadata"]["skipped_count"] == 2
    assert response["import_record"]["item_count"] == 2
    assert response["import_record"]["label_count"] == 2
    assert [item["text"] for item in response["created_items"]] == ["mi casa", "el agua"]
    assert [label["type"] for label in response["created_labels"]] == ["pos", "pos"]
    assert [label["value"]["tags"] for label in response["created_labels"]] == ["PRON NOUN", "DET NOUN"]


def test_specialized_csv_import_fails_when_required_headers_are_missing(client) -> None:
    dataset = client.get("/datasets").get_json()[0]

    response = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={
            "source_type": "csv",
            "import_kind": "pos",
            "text": "text,label\nhello,NOUN\n",
        },
    ).get_json()

    assert response["job"]["status"] == "failed"
    assert "POS CSV requires columns: text,tags" in response["job"]["error"]
    assert response["import_record"]["status"] == "failed"
    assert response["import_record"]["item_count"] == 0
    assert response["import_record"]["label_count"] == 0


def test_delete_dataset_removes_workspace_state(client) -> None:
    dataset = client.post(
        "/datasets",
        json={"name": "Zapotec pilot", "language_code": "zap", "language_name": "Zapotec"},
    ).get_json()
    import_response = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={"text": "uno dos tres", "source_type": "text"},
    ).get_json()
    research_response = client.post(f"/datasets/{dataset['id']}/research").get_json()
    suggestions = client.post(f"/datasets/{dataset['id']}/pos-suggestions", json={"limit": 5}).get_json()["suggestions"]

    response = client.delete(f"/datasets/{dataset['id']}")

    assert response.status_code == 204
    assert all(item["id"] != dataset["id"] for item in client.get("/datasets").get_json())
    assert client.get(f"/datasets/{dataset['id']}/dashboard").status_code == 404
    assert client.get(f"/jobs/{import_response['job']['id']}").status_code == 404
    assert client.get(f"/jobs/{research_response['job']['id']}").status_code == 404
    assert client.patch(f"/suggestions/{suggestions[0]['id']}", json={"action": "accepted"}).status_code == 404


def test_delete_unknown_dataset_returns_404(client) -> None:
    response = client.delete("/datasets/ds_missing")

    assert response.status_code == 404


def test_translation_demo_fallback(client) -> None:
    response = client.post("/models/nahuatl/translate", json={"text": "muchas flores son blancas"}).get_json()

    assert response["output_text"] == "miak xochitl istak"
    assert response["provider"] == "local-demo"
    assert response["used_fallback"] is True
    assert response["warning"]["provider"] == "aws-neuron-endpoint"
