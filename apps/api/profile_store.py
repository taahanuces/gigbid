from __future__ import annotations

import re

from langgraph.store.base import BaseStore

from apps.api.schemas.api import ProfileSettings

SAFE_LABEL = re.compile(r"[^A-Za-z0-9_-]")
PROFILE_KEY = "settings"


def _label(value: str) -> str:
    return SAFE_LABEL.sub("_", value)[:120] or "unknown"


def profile_namespace(tenant_id: str, user_id: str) -> tuple[str, ...]:
    return ("gigbid", _label(tenant_id), _label(user_id), "profile")


async def load_profile(
    store: BaseStore | None,
    *,
    tenant_id: str,
    user_id: str,
) -> ProfileSettings:
    if store is None:
        return ProfileSettings()
    item = await store.aget(profile_namespace(tenant_id, user_id), PROFILE_KEY)
    if item is None:
        return ProfileSettings()
    return ProfileSettings.model_validate(item.value)


async def save_profile(
    store: BaseStore,
    *,
    tenant_id: str,
    user_id: str,
    settings: ProfileSettings,
) -> ProfileSettings:
    normalized = settings.model_copy(
        update={
            "search_keywords": list(
                dict.fromkeys(
                    keyword.strip().lower()
                    for keyword in settings.search_keywords
                    if keyword.strip()
                )
            )[:20]
        }
    )
    await store.aput(
        profile_namespace(tenant_id, user_id),
        PROFILE_KEY,
        normalized.model_dump(mode="json"),
        index=False,
    )
    return normalized
