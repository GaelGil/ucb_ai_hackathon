import pytest
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from app.src.api import create_app
from app.src.config import Settings


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    settings = Settings(database_url="sqlite://", seed_demo_data=True)
    return create_app(settings=settings, engine=engine, create_tables=True).test_client()


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


def test_research_fallback_is_visible_in_metadata(client) -> None:
    dataset = client.get("/datasets").get_json()[0]

    response = client.post(f"/datasets/{dataset['id']}/research").get_json()

    assert response["job"]["metadata"]["used_fallback"] is True
    assert response["job"]["metadata"]["warnings"]
    assert response["research"]["warnings"]


def test_research_is_separate_by_type(client) -> None:
    dataset = client.get("/datasets").get_json()[0]

    pos = client.post(f"/datasets/{dataset['id']}/research", query_string={"type": "pos"}).get_json()
    translation = client.post(f"/datasets/{dataset['id']}/research", query_string={"type": "translation"}).get_json()

    assert pos["research"]["id"] != translation["research"]["id"]
    assert pos["research"]["type"] == "pos"
    assert translation["research"]["type"] == "translation"
    assert translation["job"]["metadata"]["research_type"] == "translation"


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
