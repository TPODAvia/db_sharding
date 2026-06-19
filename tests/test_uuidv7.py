from uuid import UUID

from app.common.uuidv7 import new_uuidv7


def test_uuidv7_returns_uuid_version_7() -> None:
    value = new_uuidv7()
    assert isinstance(value, UUID)
    assert value.version == 7
