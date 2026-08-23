from fastapi.testclient import TestClient

from groundguard.api.app import app


client = TestClient(app)


def test_dashboard_is_available():
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "GroundGuard" in response.text
    assert "Evaluate an Answer" in response.text


def test_dashboard_contains_evaluation_fields():
    response = client.get("/dashboard")

    assert response.status_code == 200

    html = response.text

    assert 'id="question"' in html
    assert 'id="context"' in html
    assert 'id="answer"' in html
    assert 'id="threshold"' in html


def test_dashboard_contains_result_fields():
    response = client.get("/dashboard")

    assert response.status_code == 200

    html = response.text

    assert 'id="decision"' in html
    assert 'id="reliability"' in html
    assert 'id="grounding"' in html
    assert 'id="relevance"' in html
    assert 'id="contradiction"' in html
    assert 'id="pii"' in html
    assert 'id="prompt-injection"' in html
    assert 'id="safety"' in html
    assert 'id="reason"' in html