"""
Integration tests for the /avatar/chat endpoint.
Run with: pytest tests/test_avatar.py -v
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_avatar_simple_reply():
    payload = {
        "messages": [{"role": "user", "content": "Hola, mi perro ladra mucho por las noches."}]
    }
    response = client.post("/avatar/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert len(data["reply"]) > 10


def test_avatar_multi_turn():
    payload = {
        "messages": [
            {"role": "user", "content": "My dog is a 2-year-old Labrador."},
            {"role": "assistant", "content": "Great! What's the issue you're seeing?"},
            {"role": "user", "content": "He pulls on the leash every walk."},
        ]
    }
    response = client.post("/avatar/chat", json=payload)
    assert response.status_code == 200
    assert response.json()["reply"]


def test_avatar_last_message_must_be_user():
    payload = {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
    }
    response = client.post("/avatar/chat", json=payload)
    assert response.status_code == 422


def test_avatar_empty_messages():
    response = client.post("/avatar/chat", json={"messages": []})
    assert response.status_code == 422
