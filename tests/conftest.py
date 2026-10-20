"""Fixtures available to every test file. pytest loads conftest.py automatically."""

import pytest

from caregraph import db


@pytest.fixture
def conn():
    # A fixture is setup code pytest runs for any test that asks for it by name.
    # ":memory:" gives a fresh, empty database that never touches data/caregraph.db.
    connection = db.connect(":memory:")
    yield connection
    connection.close()
