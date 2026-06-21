import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from app.src.api import create_app
from app.src.config import Settings


@pytest.fixture
def client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    settings = Settings(database_url="sqlite://", seed_demo_data=True)
    return TestClient(create_app(settings=settings, engine=engine, create_tables=True))


def test_text_pos_research_review_and_training_flow(client: TestClient) -> None:
    dataset = client.post(
        "/datasets",
        json={"name": "Mixtec pilot", "language_code": "mix", "language_name": "Mixtec"},
    ).json()

    imported = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={"text": "la casa grande\nel agua corre rapido", "source_type": "text"},
    ).json()
    assert imported["import_record"]["item_count"] == 2

    research = client.post(f"/datasets/{dataset['id']}/research").json()
    assert research["research"]["id"].startswith("research_")

    suggestions = client.post(f"/datasets/{dataset['id']}/pos-suggestions", json={"limit": 5}).json()["suggestions"]
    assert len(suggestions) == 2
    assert suggestions[0]["research_id"] == research["research"]["id"]
    assert suggestions[0]["tokens"]

    reviewed = client.patch(f"/suggestions/{suggestions[0]['id']}", json={"action": "accepted"}).json()
    assert reviewed["status"] == "accepted"

    labels = client.get(f"/datasets/{dataset['id']}/labels", params={"type": "pos"}).json()["labels"]
    assert len(labels) == 1
    assert labels[0]["source"] == "ai_accepted"

    trained = client.post(
        f"/datasets/{dataset['id']}/pos-model/train",
        json={"minimum_examples": 20, "demo_override": True},
    ).json()
    assert trained["pos_model"]["status"] == "ready"
    assert trained["pos_model"]["accepted_sentence_count"] == 1


def test_research_is_cached_per_dataset_language(client: TestClient) -> None:
    dataset = client.get("/datasets").json()[0]

    first = client.post(f"/datasets/{dataset['id']}/research").json()
    second = client.post(f"/datasets/{dataset['id']}/research").json()

    assert first["research"]["id"] == second["research"]["id"]
    assert second["job"]["metadata"]["cached"] is True


def test_csv_import_uses_text_column(client: TestClient) -> None:
    dataset = client.get("/datasets").json()[0]

    response = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={"source_type": "csv", "text": "id,text\n1,hello world\n2,second row\n"},
    ).json()

    assert response["import_record"]["item_count"] == 2
    assert response["import_record"]["label_count"] == 0
    assert [item["text"] for item in response["created_items"]] == ["hello world", "second row"]


def test_csv_import_can_create_labels(client: TestClient) -> None:
    dataset = client.get("/datasets").json()[0]

    response = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={
            "source_type": "csv",
            "text": "id,text,translation,emotion\n1,hello world,tlasohkamati,happy\n2,second row,ome,neutral\n",
        },
    ).json()

    assert response["import_record"]["item_count"] == 2
    assert response["import_record"]["label_count"] == 4
    assert {label["source"] for label in response["created_labels"]} == {"csv_import"}

    translations = client.get(f"/datasets/{dataset['id']}/labels", params={"type": "translation"}).json()["labels"]
    assert [label["value"]["text"] for label in translations] == ["tlasohkamati", "ome"]
    assert [label["data_text"] for label in translations] == ["hello world", "second row"]


def test_translation_csv_import_uses_required_columns(client: TestClient) -> None:
    dataset = client.get("/datasets").json()[0]

    response = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={
            "source_type": "csv",
            "import_kind": "translation",
            "text": (
                "text,translation,source,src,target\n"
                "hello world,tlasohkamati,axolotl,sp,nah\n"
                "missing translation,,axolotl,sp,nah\n"
            ),
        },
    ).json()

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
        "src": "sp",
        "target": "nah",
    }


def test_pos_csv_import_accepts_text_tags_and_json_list_tags(client: TestClient) -> None:
    dataset = client.get("/datasets").json()[0]

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
    ).json()

    assert response["job"]["status"] == "succeeded"
    assert response["job"]["metadata"]["import_kind"] == "pos"
    assert response["job"]["metadata"]["skipped_count"] == 2
    assert response["import_record"]["item_count"] == 2
    assert response["import_record"]["label_count"] == 2
    assert [item["text"] for item in response["created_items"]] == ["mi casa", "el agua"]
    assert [label["type"] for label in response["created_labels"]] == ["pos", "pos"]
    assert [label["value"]["tags"] for label in response["created_labels"]] == ["PRON NOUN", "DET NOUN"]


def test_specialized_csv_import_fails_when_required_headers_are_missing(client: TestClient) -> None:
    dataset = client.get("/datasets").json()[0]

    response = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={
            "source_type": "csv",
            "import_kind": "pos",
            "text": "text,label\nhello,NOUN\n",
        },
    ).json()

    assert response["job"]["status"] == "failed"
    assert "POS CSV requires columns: text,tags" in response["job"]["error"]
    assert response["import_record"]["status"] == "failed"
    assert response["import_record"]["item_count"] == 0
    assert response["import_record"]["label_count"] == 0


def test_delete_dataset_removes_workspace_state(client: TestClient) -> None:
    dataset = client.post(
        "/datasets",
        json={"name": "Zapotec pilot", "language_code": "zap", "language_name": "Zapotec"},
    ).json()
    import_response = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={"text": "uno dos tres", "source_type": "text"},
    ).json()
    research_response = client.post(f"/datasets/{dataset['id']}/research").json()
    suggestions = client.post(f"/datasets/{dataset['id']}/pos-suggestions", json={"limit": 5}).json()["suggestions"]

    response = client.delete(f"/datasets/{dataset['id']}")

    assert response.status_code == 204
    assert all(item["id"] != dataset["id"] for item in client.get("/datasets").json())
    assert client.get(f"/datasets/{dataset['id']}/dashboard").status_code == 404
    assert client.get(f"/jobs/{import_response['job']['id']}").status_code == 404
    assert client.get(f"/jobs/{research_response['job']['id']}").status_code == 404
    assert client.patch(f"/suggestions/{suggestions[0]['id']}", json={"action": "accepted"}).status_code == 404


def test_delete_unknown_dataset_returns_404(client: TestClient) -> None:
    response = client.delete("/datasets/ds_missing")

    assert response.status_code == 404


def test_translation_demo_fallback(client: TestClient) -> None:
    response = client.post("/models/nahuatl/translate", json={"text": "muchas flores son blancas"}).json()

    assert response["output_text"] == "miak xochitl istak"
    assert response["provider"] == "local-demo"
