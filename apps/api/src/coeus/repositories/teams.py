"""Persistence for organisational teams, profiles and team calendars.

Same shape as the other seed repositories: an in-memory dict cache backed by
the JSON state store with copy-on-write saves, restored on startup and
seeded when the namespace is empty.
"""

from collections.abc import Mapping
from threading import RLock
from typing import cast
from uuid import UUID

from coeus.domain.teams import OrgTeam, TeamCalendarEntry, UserProfile
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore

TEAMS_NAMESPACE = "teams"
CALENDAR_NAMESPACE = "team_calendar"
PROFILES_NAMESPACE = "user_profiles"


class TeamRepository:
    def __init__(self, state_store: StateStore | None = None) -> None:
        self._state_store = state_store
        self._lock = RLock()
        self._teams: dict[UUID, OrgTeam] = {}
        self._entries: dict[UUID, TeamCalendarEntry] = {}
        self._profiles: dict[UUID, UserProfile] = {}
        self._restore()

    def list_teams(self) -> tuple[OrgTeam, ...]:
        with self._lock:
            return tuple(sorted(self._teams.values(), key=lambda team: team.name))

    def get_team(self, team_id: UUID) -> OrgTeam | None:
        with self._lock:
            return self._teams.get(team_id)

    def save_team(self, team: OrgTeam) -> None:
        with self._lock:
            previous = dict(self._teams)
            self._teams[team.team_id] = team
            self._persist_or_rollback(TEAMS_NAMESPACE, previous)

    def list_entries(self, team_id: UUID) -> tuple[TeamCalendarEntry, ...]:
        with self._lock:
            entries = (entry for entry in self._entries.values() if entry.team_id == team_id)
            return tuple(sorted(entries, key=lambda entry: (entry.entry_date, entry.created_at)))

    def save_entry(self, entry: TeamCalendarEntry) -> None:
        with self._lock:
            previous = dict(self._entries)
            self._entries[entry.entry_id] = entry
            self._persist_or_rollback(CALENDAR_NAMESPACE, previous)

    def delete_entry(self, entry_id: UUID) -> TeamCalendarEntry | None:
        with self._lock:
            previous = dict(self._entries)
            removed = self._entries.pop(entry_id, None)
            if removed is not None:
                self._persist_or_rollback(CALENDAR_NAMESPACE, previous)
            return removed

    def get_entry(self, entry_id: UUID) -> TeamCalendarEntry | None:
        with self._lock:
            return self._entries.get(entry_id)

    def get_profile(self, user_id: UUID) -> UserProfile | None:
        with self._lock:
            return self._profiles.get(user_id)

    def save_profile(self, profile: UserProfile) -> None:
        with self._lock:
            previous = dict(self._profiles)
            self._profiles[profile.user_id] = profile
            self._persist_or_rollback(PROFILES_NAMESPACE, previous)

    def delete_profile(self, user_id: UUID) -> UserProfile | None:
        with self._lock:
            previous = dict(self._profiles)
            removed = self._profiles.pop(user_id, None)
            if removed is not None:
                self._persist_or_rollback(PROFILES_NAMESPACE, previous)
            return removed

    def _persist_or_rollback(self, namespace: str, previous: Mapping[UUID, object]) -> None:
        try:
            self._persist(namespace)
        except Exception:
            if namespace == TEAMS_NAMESPACE:
                self._teams = dict(cast(Mapping[UUID, OrgTeam], previous))
            elif namespace == CALENDAR_NAMESPACE:
                self._entries = dict(cast(Mapping[UUID, TeamCalendarEntry], previous))
            else:
                self._profiles = dict(cast(Mapping[UUID, UserProfile], previous))
            raise

    def _persist(self, namespace: str) -> None:
        if self._state_store is None:
            return
        if namespace == TEAMS_NAMESPACE:
            self._state_store.save(
                namespace,
                {
                    "items": [
                        encode_value(team)
                        for team in sorted(self._teams.values(), key=lambda team: str(team.team_id))
                    ]
                },
            )
            return
        if namespace == CALENDAR_NAMESPACE:
            self._state_store.save(
                namespace,
                {
                    "items": [
                        encode_value(entry)
                        for entry in sorted(
                            self._entries.values(), key=lambda entry: str(entry.entry_id)
                        )
                    ]
                },
            )
            return
        self._state_store.save(
            namespace,
            {
                "items": [
                    encode_value(profile)
                    for profile in sorted(
                        self._profiles.values(), key=lambda profile: str(profile.user_id)
                    )
                ]
            },
        )

    def _restore(self) -> None:
        if self._state_store is None:
            return
        teams = cast(tuple[OrgTeam, ...], self._load(TEAMS_NAMESPACE))
        self._teams = {team.team_id: team for team in teams}
        entries = cast(tuple[TeamCalendarEntry, ...], self._load(CALENDAR_NAMESPACE))
        self._entries = {entry.entry_id: entry for entry in entries}
        profiles = cast(tuple[UserProfile, ...], self._load(PROFILES_NAMESPACE))
        self._profiles = {profile.user_id: profile for profile in profiles}

    def _load(self, namespace: str) -> tuple[object, ...]:
        payload = self._state_store.load(namespace) if self._state_store else None
        if payload is None:
            return ()
        return tuple(decode_value(item) for item in payload.get("items", []))
