import re

from fastapi import HTTPException, status

_WORKSPACE_ID_PATTERN = re.compile(r"^\d{16}$")


def normalize_workspace_id(workspace_id: str) -> str:
    if not _WORKSPACE_ID_PATTERN.fullmatch(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="workspace_id must be exactly 16 numeric characters",
        )
    return workspace_id