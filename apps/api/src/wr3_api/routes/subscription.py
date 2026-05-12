"""Subscription endpoints — read-only from the client side.

Writes happen exclusively via the Telegram webhook's successful_payment
handler. There is intentionally no `POST /v1/subscription` here: the source
of truth is the payment provider, not the client.

  GET /v1/subscription/me   Current user's active subscription (or free)
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from wr3_api.auth import current_user_required
from wr3_api.models import User
from wr3_api.models.subscription import STARS_PRICE
from wr3_api.services import subscription_repository as sub_repo

logger = structlog.get_logger()
router = APIRouter()


@router.get("/me")
async def my_subscription(user: User = Depends(current_user_required)) -> dict[str, Any]:
    sub = await sub_repo.get_active_for_user(user.id)
    return {
        **sub_repo.subscription_to_dict(sub),
        # `tier` is the canonical thing the Mini App should display in the
        # header. We expose both so the client doesn't have to map plan→tier.
        "tier": user.tier,
    }


@router.get("/plans")
async def list_plans() -> dict[str, Any]:
    """Public catalogue of buyable plans + their Stars price.

    Mirrors `STARS_PRICE` — single source of truth lives in the model file.
    The Mini App / pricing page can read this to show live prices without
    duplicating the dict on the frontend.
    """
    return {
        "plans": [
            {"plan": plan, "stars": stars}
            for plan, stars in STARS_PRICE.items()
        ],
        "currency": "XTR",
        "period_days": 30,
    }
