from __future__ import annotations

from fastapi import APIRouter

from api.schemas import TaxonomyOut
from app.taxonomy import TAXONOMY

router = APIRouter(prefix="/api/taxonomy", tags=["taxonomy"])


@router.get("", response_model=TaxonomyOut)
def get_taxonomy() -> TaxonomyOut:
    return TaxonomyOut(taxonomy={topic: list(subs) for topic, subs in TAXONOMY.items()})
