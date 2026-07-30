"""
conftest.py — shared pytest fixtures.

Key design choice: these tests never touch the real Neon database. save_booking
is mocked out (see mock_save_booking below) so running the test suite is fast,
free, and never writes junk rows into production data — the same discipline
we'd want in the actual database, applied to testing it.
"""

import os
import sys
from unittest.mock import patch

import pytest

# Make sure app.py (at the repo root) is importable regardless of where
# pytest is invoked from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

# app.py may reference these at module level (e.g. stripe.api_key = ...).
# Safe fallback values so import doesn't fail in a test environment that
# doesn't have the real .env loaded.
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql://fake:fake@localhost/fake")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_fake")

import app as flask_app_module  # noqa: E402  (must come after env vars are set)

API_KEY = os.environ["APP_SECRET_KEY"]


@pytest.fixture
def client():
    flask_app_module.app.config["TESTING"] = True
    with flask_app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def mock_save_booking():
    """Prevents tests from writing to Neon — returns a fake booking id instead."""
    with patch("app.save_booking", return_value=999) as mock:
        yield mock
