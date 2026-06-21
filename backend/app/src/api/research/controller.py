from __future__ import annotations

from flask import Blueprint, request

from app.src.api.dependencies import get_research_service
from app.src.api.responses import json_abort, json_response
from app.src.database.models.research import ResearchType
from app.src.models import ResearchResponse


bp = Blueprint("research", __name__)


def _research_type() -> ResearchType:
    raw = request.args.get("type")
    if raw is None:
        return ResearchType.pos
    try:
        return ResearchType(raw)
    except ValueError:
        json_abort(422, f"Invalid research type: {raw}")


def _force() -> bool:
    return request.args.get("force", "false").strip().lower() in {"true", "1", "yes", "on"}


@bp.post("/datasets/<dataset_id>/research")
def create_research(dataset_id: str):
    research, job = get_research_service().ensure_research(
        dataset_id, force=_force(), research_type=_research_type()
    )
    return json_response(ResearchResponse(research=research, job=job))


@bp.get("/datasets/<dataset_id>/research")
def get_research(dataset_id: str):
    research_type = _research_type()
    research = get_research_service().get_research(dataset_id, research_type=research_type)
    if research is None:
        json_abort(404, f"{research_type.value} research has not been generated for this dataset.")
    return json_response(research)


# TODO: See google doc for reference
# Implement two endpoints
# endpoit calls agents
# angent returns list of sentences
# another one returns notes on a language.
