from dataclasses import asdict
from typing import Any

from fastapi import APIRouter

from app.core.errors import NotFoundError
from app.domain.exceptions import RunNotFoundError
from app.interfaces.api.deps import GetRunStatusDep

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    use_case: GetRunStatusDep,
) -> dict[str, Any]:
    try:
        result = await use_case.execute(run_id)
    except RunNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc

    return asdict(result)
