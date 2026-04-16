"""
Integration tests for the /analysis endpoint.
Requires a running Qdrant instance and valid API keys in .env.
Run with: pytest tests/test_analysis.py -v
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_ANAMNESIS = {
    "dog_name": "Max",
    "dog_age": "3 years",
    "breed": "Border Collie",
    "weaning_age_weeks": 8,
    "chronic_disease": False,
    "living_environment": "inside",
    "household_members": 2,
    "children_present": False,
    "other_dogs": False,
    "problem_description": (
        "Max barks intensely and scratches the door every time we leave the "
        "apartment. Neighbours complain. He also destroys cushions."
    ),
    "when_it_happens": "When we leave the apartment, even for 5 minutes",
    "frequency": "high",
    "where_it_happens": "Living room, near the front door",
    "who_is_present": "No one — owner is away",
    "involves_aggression": False,
    "previous_attempts": "We tried leaving the radio on",
    "owner_theory": "He misses us and is bored",
}


def test_analysis_returns_200():
    response = client.post("/analysis", json=SAMPLE_ANAMNESIS)
    assert response.status_code == 200


def test_analysis_has_required_fields():
    response = client.post("/analysis", json=SAMPLE_ANAMNESIS)
    data = response.json()
    assert "analysis" in data
    assert "sources" in data
    assert "input_tokens" in data
    assert "output_tokens" in data
    assert len(data["analysis"]) > 100


def test_analysis_missing_required_field():
    bad_payload = {k: v for k, v in SAMPLE_ANAMNESIS.items() if k != "dog_name"}
    response = client.post("/analysis", json=bad_payload)
    assert response.status_code == 422
