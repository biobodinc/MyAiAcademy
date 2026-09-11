from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from myai_core.db.models import Preference
from myai_core.preferences.schemas import ADVANCED_KEYS, Preferences, PreferencesUpdate


class PreferencesService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> Preferences:
        rows = self._session.scalars(select(Preference)).all()
        raw = {row.key: row.value for row in rows}
        # Unknown keys (from a newer/older version) are ignored; invalid values fall back
        # to defaults rather than breaking startup.
        known = {k: v for k, v in raw.items() if k in Preferences.model_fields}
        try:
            return Preferences.model_validate(known)
        except ValueError:
            return Preferences()

    def update(self, changes: PreferencesUpdate) -> Preferences:
        payload = changes.model_dump(exclude_unset=True)
        # ``None`` means "not provided" for ordinary fields but "clear it" for advanced
        # overrides, which are nullable by design.
        payload = {k: v for k, v in payload.items() if v is not None or k in ADVANCED_KEYS}
        # Validate the merged result before persisting anything.
        merged = self.get().model_copy(update=payload)
        Preferences.model_validate(merged.model_dump())
        for key, value in payload.items():
            row = self._session.get(Preference, key)
            serialised = value.value if hasattr(value, "value") else value
            if row is None:
                self._session.add(Preference(key=key, value=serialised))
            else:
                row.value = serialised
        self._session.flush()
        return merged
