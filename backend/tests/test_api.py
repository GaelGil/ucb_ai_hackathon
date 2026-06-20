from fastapi.testclient import TestClient

from app.repositories import InMemoryRepository
from app.src.api import create_app


def test_text_pos_research_review_and_training_flow() -> None:
    client = TestClient(create_app(InMemoryRepository()))

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

    reviewed = client.patch(f"/suggestions/{suggestions[0]['id']}", json={"action": "approved"}).json()
    assert reviewed["status"] == "approved"

    trained = client.post(
        f"/datasets/{dataset['id']}/pos-model/train",
        json={"minimum_examples": 20, "demo_override": True},
    ).json()
    assert trained["pos_model"]["status"] == "ready"
    assert trained["pos_model"]["accepted_sentence_count"] == 1


def test_research_is_cached_per_dataset_language() -> None:
    client = TestClient(create_app(InMemoryRepository()))
    dataset = client.get("/datasets").json()[0]

    first = client.post(f"/datasets/{dataset['id']}/research").json()
    second = client.post(f"/datasets/{dataset['id']}/research").json()

    assert first["research"]["id"] == second["research"]["id"]
    assert second["job"]["metadata"]["cached"] is True


def test_csv_import_uses_text_column() -> None:
    client = TestClient(create_app(InMemoryRepository()))
    dataset = client.get("/datasets").json()[0]

    response = client.post(
        f"/datasets/{dataset['id']}/imports",
        json={"source_type": "csv", "text": "id,text\n1,hello world\n2,second row\n"},
    ).json()

    assert response["import_record"]["item_count"] == 2
    assert [item["text"] for item in response["created_items"]] == ["hello world", "second row"]


def test_delete_dataset_removes_workspace_state() -> None:
    client = TestClient(create_app(InMemoryRepository()))

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
    assert client.patch(f"/suggestions/{suggestions[0]['id']}", json={"action": "approved"}).status_code == 404


def test_delete_unknown_dataset_returns_404() -> None:
    client = TestClient(create_app(InMemoryRepository()))

    response = client.delete("/datasets/ds_missing")

    assert response.status_code == 404


def test_translation_demo_fallback() -> None:
    client = TestClient(create_app(InMemoryRepository()))

    response = client.post("/models/nahuatl/translate", json={"text": "muchas flores son blancas"}).json()

    assert response["output_text"] == "miak xochitl istak"
    assert response["provider"] == "local-demo"
