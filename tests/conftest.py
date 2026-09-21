import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from database.seed import seed
from models import db


@pytest.fixture()
def app(tmp_path):
    # Optional MySQL testing: only use a disposable database. Tables are dropped.
    database_url = os.getenv(
        "TEST_DATABASE_URL", "sqlite:///" + str(tmp_path / "test.db")
    )
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only",
            "SQLALCHEMY_DATABASE_URI": database_url,
            "WTF_CSRF_ENABLED": False,
            "ADMIN_REGISTRATION_CODE": "test-invite",
        }
    )
    with application.app_context():
        db.create_all()
        seed()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def login(client):
    def perform(role="donor"):
        client.post("/logout")
        return client.post(
            "/login",
            data={"email": role + "@foodconnect.demo", "password": "Demo@12345"},
            follow_redirects=True,
        )

    return perform
