from fastapi.testclient import TestClient

from groundguard.api.app import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_evaluate_rejects_empty_question():
    response = client.post(
        "/evaluate",
        json={
            "question": "",
            "context": "The company was founded in 2018.",
            "answer": "The company was founded in 2018.",
        },
    )

    assert response.status_code == 422


def test_evaluate_rejects_empty_context():
    response = client.post(
        "/evaluate",
        json={
            "question": "When was the company founded?",
            "context": "",
            "answer": "The company was founded in 2018.",
        },
    )

    assert response.status_code == 422


def test_evaluate_rejects_empty_answer():
    response = client.post(
        "/evaluate",
        json={
            "question": "When was the company founded?",
            "context": "The company was founded in 2018.",
            "answer": "",
        },
    )

    assert response.status_code == 422


def test_evaluate_rejects_invalid_threshold():
    response = client.post(
        "/evaluate",
        json={
            "question": "When was the company founded?",
            "context": "The company was founded in 2018.",
            "answer": "The company was founded in 2018.",
            "threshold": 1.01,
        },
    )

    assert response.status_code == 422


def test_evaluate_rejects_negative_threshold():
    response = client.post(
        "/evaluate",
        json={
            "question": "When was the company founded?",
            "context": "The company was founded in 2018.",
            "answer": "The company was founded in 2018.",
            "threshold": -0.01,
        },
    )

    assert response.status_code == 422


def test_evaluate_returns_complete_decision():
    response = client.post(
        "/evaluate",
        json={
            "question": "When was the company founded?",
            "context": "The company was founded in 2018.",
            "answer": "The company was founded in 2018.",
        },
    )

    assert response.status_code == 200

    data = response.json()

    required_fields = {
        "label",
        "reliable",
        "system_decision",
        "grounding_score",
        "relevance_score",
        "contradiction_score",
        "reliability_score",
        "threshold",
        "grounding_label",
        "relevance_label",
        "contradiction_label",
        "pii_detected",
        "pii_categories",
        "prompt_injection_detected",
        "safety_safe",
        "safety_evidence",
        "reason",
    }

    assert required_fields.issubset(data.keys())