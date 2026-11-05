# SPDX-License-Identifier: AGPL-3.0-only
"""Stage 5 experimental Local AI source selection and index admission policy.

Pure policy only. This module NEVER reads user documents, opens a ZIM, creates
embeddings, writes an index, checks real disk mounts, or starts background jobs.
An authenticated server must supply owner-scoped source inventory/grants and
trusted storage observations before invoking it; browser-supplied claims are
not sufficient authorization. Stage 5 design is not yet fully approved.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Iterable

KINDS = ("file", "folder", "collection", "user_data", "kolibri", "browser", "wikipedia")
INDEX_MODES = frozenset(("none", "keyword", "semantic"))
STORAGE_KINDS = frozenset(("internal", "external"))


@dataclass(frozen=True)
class KnowledgeSource:
    source_id: str
    kind: str
    label: str
    owner_id: str | None = None
    available: bool = True

    def __post_init__(self) -> None:
        if (not self.source_id or not self.label or self.kind not in KINDS
                or (self.kind != "wikipedia" and not self.owner_id)):
            raise ValueError("Invalid source inventory entry")
        if self.kind == "wikipedia" and self.owner_id is not None:
            raise ValueError("Shared Wikipedia must not be scoped as a private file")


class SourceSelector:
    """Select multiple source IDs, never treating selection as a new ACL grant."""

    def __init__(self, inventory: Iterable[KnowledgeSource]):
        sources = tuple(inventory)
        if len({s.source_id for s in sources}) != len(sources):
            raise ValueError("Duplicate source ID")
        self._sources = {s.source_id: s for s in sources}

    def select(self, owner_id: str, requested_ids: Collection[str], *,
               trusted_file_grants: Collection[str] = ()) -> tuple[KnowledgeSource, ...]:
        if not owner_id:
            raise ValueError("An authenticated owner identity is required")
        requested = tuple(requested_ids)
        if len(set(requested)) != len(requested):
            raise ValueError("Duplicate selected source")
        grants = frozenset(trusted_file_grants)
        result = []
        for source_id in requested:
            source = self._sources.get(source_id)
            if source is None:
                raise ValueError("Unknown source ID")
            if source.kind != "wikipedia":
                if source.owner_id != owner_id or source_id not in grants:
                    raise PermissionError("Private source not authorized for this owner")
            if not source.available:
                raise ValueError("Selected source unavailable")
            result.append(source)
        # Wikipedia is ALWAYS independent and last, including multiple wiki ZIMs.
        return tuple(sorted(result, key=lambda s: (KINDS.index(s.kind), s.label.casefold(),
                                                   s.source_id)))


@dataclass(frozen=True)
class IndexIntent:
    """Separate opt-ins: persist index, background jobs, folder watch and boot."""

    source_id: str
    mode: str = "none"  # native Kiwix/direct document retrieval remains possible
    background: bool = False
    watch_changes: bool = False
    start_after_reboot: bool = False
    storage_kind: str = "internal"
    storage_uuid: str | None = None
    estimated_peak_bytes: int = 0
    quota_bytes: int = 0

    def __post_init__(self) -> None:
        if not self.source_id or self.mode not in INDEX_MODES:
            raise ValueError("Invalid indexing mode/source")
        if self.storage_kind not in STORAGE_KINDS:
            raise ValueError("Invalid index volume class")
        if self.storage_kind == "external" and not self.storage_uuid:
            raise ValueError("An external SSD needs a selected stable UUID")
        if self.storage_kind == "internal" and self.storage_uuid is not None:
            raise ValueError("Internal index target must not use an external SSD UUID")
        if self.mode == "none" and (self.background or self.watch_changes
                                    or self.start_after_reboot):
            raise ValueError("Cannot schedule a disabled index")
        if self.watch_changes and not self.background:
            raise ValueError("Folder watch requires explicit background consent")
        if self.start_after_reboot and not self.background:
            raise ValueError("Startup requires separately enabled background indexing")
        if self.estimated_peak_bytes < 0 or self.quota_bytes < 0:
            raise ValueError("Index sizes must not be negative")


@dataclass(frozen=True)
class StorageObservation:
    """Trusted server-side volume check, NOT data from a browser form."""

    kind: str
    volume_uuid: str | None
    mounted: bool
    writable: bool
    filesystem_supported: bool
    free_bytes: int
    reserve_bytes: int = 0


@dataclass(frozen=True)
class IndexDecision:
    state: str
    reason: str
    source_id: str

    @property
    def can_start(self) -> bool:
        return self.state == "eligible_for_real_backend"


def prepare_index_job(selected: tuple[KnowledgeSource, ...], intent: IndexIntent, *,
                      explicit_owner_approval: bool = False,
                      hard_enabled: bool = False, background_allowed: bool = False,
                      startup_allowed: bool = False,
                      storage: StorageObservation | None = None) -> IndexDecision:
    """Check intent against trusted service/volume state; does not start a job.

    An eventual execution adapter must also verify mount identity and path
    containment at actual write time, enforce quotas, obtain a lock, and
    implement pause/cancel/flush. No paths or disk writes are accepted here.
    """
    source = next((s for s in selected if s.source_id == intent.source_id), None)
    if source is None:
        return IndexDecision("source_not_selected", "Source not selected/authorized", intent.source_id)
    if intent.mode == "none":
        return IndexDecision("direct_only", "No persistent index requested", intent.source_id)
    if not explicit_owner_approval:
        return IndexDecision("approval_required", "Explicit indexing permission required",
                             intent.source_id)
    if not hard_enabled:
        return IndexDecision("hard_disabled", "Index worker disabled by owner policy",
                             intent.source_id)
    if intent.watch_changes and source.kind not in ("folder", "collection", "user_data"):
        return IndexDecision("watch_unsupported", "Only permitted folder/collection sources may be watched",
                             intent.source_id)
    if intent.background and not background_allowed:
        return IndexDecision("background_disabled", "Background service policy disallows this job",
                             intent.source_id)
    if intent.start_after_reboot and not startup_allowed:
        return IndexDecision("startup_disabled", "No permission for restart-time indexing",
                             intent.source_id)
    if storage is None or not storage.mounted:
        return IndexDecision("storage_unavailable", "Trusted index volume not mounted",
                             intent.source_id)
    if (storage.kind != intent.storage_kind
            or (intent.storage_kind == "external" and
                (not storage.volume_uuid or storage.volume_uuid != intent.storage_uuid))):
        return IndexDecision("storage_mismatch", "Selected index volume UUID/kind mismatch",
                             intent.source_id)
    if not storage.writable or not storage.filesystem_supported:
        return IndexDecision("storage_incompatible", "Index volume unavailable for safe DB writes",
                             intent.source_id)
    if not intent.estimated_peak_bytes or not intent.quota_bytes:
        return IndexDecision("estimate_required", "Need verified peak index estimate and quota",
                             intent.source_id)
    if (intent.estimated_peak_bytes > intent.quota_bytes
            or intent.estimated_peak_bytes + max(0, storage.reserve_bytes)
               > storage.free_bytes):
        return IndexDecision("insufficient_space", "Quota or filesystem reserve exceeded",
                             intent.source_id)
    return IndexDecision("eligible_for_real_backend",
                         "Policy checked; no index has been created", intent.source_id)
