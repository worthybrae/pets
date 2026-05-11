"""Shared test fixtures."""

import pytest
from uuid import uuid4


@pytest.fixture
def pet_id():
    return str(uuid4())
