"""Initial OPTIONAL catalog; installed=False until an installer verifies binaries.

Core hotspot, DHCP/DNS, authentication, NVMe mounts, and recovery are excluded.
Adapters will bind these logical IDs to tested ARM64 services in later stages.
"""
from .service_manager import Module


def default_catalog() -> list[Module]:
    # idle_seconds are tentative policy defaults, not measured Pi memory numbers.
    configs = [
        ("news", (), 0),
        ("kiwix", (), 5),
        ("kolibri", (), 5),
        ("maps", (), 5),
        ("routing", ("maps",), 5),
        ("local_ai", (), 30),
        ("translator", (), 10),
        ("ocr", (), 5),
        ("asr", (), 5),
        ("tts", (), 5),
        ("browser_renderer", (), 5),
        ("radio", (), 0),
        ("tv", (), 0),
        ("radio_subtitles", ("radio", "asr"), 0),
        ("radio_translation", ("radio_subtitles", "translator"), 0),
        ("emergency_monitor", (), 0),
        ("files", (), 0),
        ("file_indexer", ("files",), 0),
        ("nextcloud_sync", ("files",), 0),
        ("pdf", (), 0),
        ("office", (), 0),
        ("media", (), 0),
        ("subtitle_studio", ("asr",), 0),
        ("nomad_utilities", (), 0),
        ("update_checker", (), 0),
    ]
    return [Module(id=name, dependencies=deps, installed=False,
                   idle_seconds=idle) for name, deps, idle in configs]
