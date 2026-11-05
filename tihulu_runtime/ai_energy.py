"""Energy-aware AI route selection; no fake remote-computer power savings."""
from __future__ import annotations

from .ai_hardware import BACKENDS, InferenceTarget, ModelSpec, choose_backend, compatibility


def route_for_energy(model: ModelSpec, targets: tuple[InferenceTarget, ...], *,
                     mode: str = 'Balanced',
                     preferred: tuple[str, ...] = BACKENDS,
                     evidence: dict[str, dict] | None = None) -> dict:
    """Eco requires measured total Pi+remote energy for EVERY compatible candidate.

    When evidence is missing, preserve user preference and label Not Tested.
    Never classify remote GPU as 'low energy' solely from the Pi's own draw.
    """
    if mode not in ('Eco', 'Balanced', 'Custom'):
        raise ValueError('Unknown energy profile')
    if set(preferred) != set(BACKENDS) or len(preferred) != len(BACKENDS):
        raise ValueError('Backend order must list each supported mode exactly once')
    compatible = [t for t in targets if compatibility(model, t)[0] == 'compatible']
    evidence = evidence or {}
    measured = []
    for target in compatible:
        key = f'{target.backend}|{model.identifier}'
        amount = evidence.get(key, {}).get('total_joules_including_remote')
        if isinstance(amount, (float, int)) and not isinstance(amount, bool) and 0 <= amount < float('inf'):
            measured.append((float(amount), target.backend))
    if mode == 'Eco' and measured and len(measured) == len(compatible):
        order = tuple(x[1] for x in sorted(measured))
        order += tuple(x for x in preferred if x not in order)
        result = choose_backend(model, targets, order=order)
        result['energy_evidence'] = 'Measured end-to-end'
        return result
    result = choose_backend(model, targets, order=preferred)
    result['energy_evidence'] = 'Not Tested' if mode == 'Eco' else 'Not required for ordering'
    return result
