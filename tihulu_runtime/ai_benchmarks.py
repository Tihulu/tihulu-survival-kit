"""Hardware-scoped local AI benchmark evidence ledger (not a benchmark runner).

Do not recommend with old Pi/GPU measurements after a hardware upgrade.
Only verified runtime workers may provide actual values; imported results are
explicitly excluded from recommendations by default.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import json
import math
import os
import tempfile

from .ai_hardware import BACKENDS, HardwareSnapshot

METRICS = frozenset((
    'tokens_per_second', 'time_to_first_token_ms', 'observed_peak_memory_bytes',
    'joules_per_response', 'turkish_score', 'multilingual_score',
    'translation_score', 'summarization_score', 'wikipedia_rag_score',
    'reasoning_score', 'overall_score'))


def hardware_key(snapshot: HardwareSnapshot, *, remote_hardware_id: str = '') -> str:
    """Capability fingerprint; excludes user paths and other private inventory."""
    data = {
        'arch': snapshot.architecture, 'board': snapshot.board,
        'ram_bytes': snapshot.system_ram_bytes,
        'hailo_pci': sorted(snapshot.hailo_pci_devices),
        'hailo_initialized': snapshot.hailo_initialized,
        'npu_ram_bytes': snapshot.dedicated_npu_ram_bytes,
        'remote_hardware_id': remote_hardware_id}
    return sha256(json.dumps(data, sort_keys=True).encode('utf8')).hexdigest()


@dataclass(frozen=True)
class BenchmarkEvidence:
    model_id: str
    model_revision: str
    backend: str
    hardware_key: str
    measured_utc: str
    source: str
    metrics: dict[str, float]

    def __post_init__(self) -> None:
        if (not self.model_id or not self.model_revision or
                self.backend not in BACKENDS or len(self.hardware_key) != 64 or
                not self.measured_utc or self.source not in ('local_benchmark', 'imported')):
            raise ValueError('Invalid benchmark identity/provenance')
        if (not self.metrics or not set(self.metrics).issubset(METRICS) or
                any(not isinstance(v, (int, float)) or isinstance(v, bool)
                    or not math.isfinite(v) or v < 0 for v in self.metrics.values())):
            raise ValueError('Invalid or missing measured metrics')
        for name, value in self.metrics.items():
            if name.endswith('_score') and value > 1:
                raise ValueError('Quality scores must be normalized to [0, 1]')


class BenchmarkLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.rows: list[BenchmarkEvidence] = []
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf8'))
            if data.get('schema') != 1:
                raise ValueError('Unsupported benchmark ledger schema')
            self.rows = [BenchmarkEvidence(**row) for row in data.get('rows', ())]

    def record(self, evidence: BenchmarkEvidence, *, owner_verified: bool = False) -> None:
        if not owner_verified:
            raise PermissionError('Trusted owner and benchmark worker required')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rows.append(evidence)
        fd, temporary = tempfile.mkstemp(prefix='.benchmarks-', dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'w', encoding='utf8') as output:
                json.dump({'schema': 1, 'rows': [asdict(x) for x in self.rows]},
                          output, indent=2)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def evidence_for(self, *, hardware_key: str, model_revisions: dict[str, str],
                     include_imported: bool = False) -> dict[str, dict]:
        """Return only same-hardware exact-revision measurements."""
        records: dict[str, dict] = {}
        for row in self.rows:
            if (row.hardware_key != hardware_key or
                model_revisions.get(row.model_id) != row.model_revision or
                (row.source != 'local_benchmark' and not include_imported)):
                continue
            records[f'{row.backend}|{row.model_id}'] = dict(row.metrics)
        return records
