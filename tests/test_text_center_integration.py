"""Synthetic Text Center shared lease tests; not real radio hardware tests."""
import unittest
from tihulu_runtime.sdr_resource_broker import SDRResourceBroker, ReceiverBusy
from tihulu_runtime.text_center_integration import TextCenterIntegration, TextCenterUnavailable


class _Reservation:
    def __init__(self, guard): self.guard = guard
    def release(self): self.guard.released += 1


class _Guard:
    def __init__(self): self.acquired = []; self.released = 0
    def reserve(self, rid, purpose):
        self.acquired.append((rid, purpose))
        return _Reservation(self)


class _Backend:
    def __init__(self): self.started = []; self.stopped = []; self.ack = True
    def start(self, **kwargs):
        self.started.append(kwargs)
        return object()
    def stop(self, handle):
        self.stopped.append(handle)
        return self.ack


class TextCenterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.broker = SDRResourceBroker()
        self.guard, self.backend = _Guard(), _Backend()
        self.bridge = TextCenterIntegration(
            broker=self.broker, guard=self.guard, backend=self.backend,
            inventory=lambda: {"rtl_usb_count": 1, "connected_decoder": False},
            catalog=lambda inv: [{"id": "fm_rds", "state": "manual_capture"}])

    def test_passive_discovery_has_no_sdr_side_effect(self):
        result = self.bridge.passive_discover(owner_id="owner", receiver_ids=("rtl-A",))
        self.assertEqual(result["status"], "passive_only")
        self.assertFalse(result["rf_receiver_tuned"])
        self.assertFalse(result["background_polling"])
        self.assertEqual(result["receivers"][0]["state"], "free")
        self.assertFalse(self.guard.acquired)
        self.assertFalse(self.backend.started)

    def test_user_permission_and_cross_process_guard_fail_closed(self):
        bridge = TextCenterIntegration(broker=self.broker, backend=self.backend)
        with self.assertRaises(TextCenterUnavailable):
            bridge.start_fm_rds(owner_id="o", receiver_id="rtl-A",
                                frequency_hz=98_600_000, duration_seconds=20,
                                user_triggered=True)
        with self.assertRaises(PermissionError):
            self.bridge.start_fm_rds(owner_id="o", receiver_id="rtl-A",
                                     frequency_hz=98_600_000, duration_seconds=20)
        with self.assertRaises(PermissionError):
            self.bridge.passive_discover(owner_id="")
        self.assertEqual(self.broker.active("rtl-A")["state"], "free")

    def test_capture_parameters_strictly_validated(self):
        for hz in (-1, 0, 109_000_000, 98.6, True):
            with self.subTest(hz=hz), self.assertRaises(ValueError):
                self.bridge.start_fm_rds(owner_id="o", receiver_id="rtl-A",
                    frequency_hz=hz, duration_seconds=20, user_triggered=True)
        for sec in (0, 91, "20", False):
            with self.subTest(duration=sec), self.assertRaises(ValueError):
                self.bridge.start_fm_rds(owner_id="o", receiver_id="rtl-A",
                    frequency_hz=98_600_000, duration_seconds=sec, user_triggered=True)

    def test_protected_adsb_lease_is_not_preempted(self):
        lease = self.broker.acquire(
            "rtl-A", app_id="flight_radar", owner_id="owner",
            purpose="1090_adsb", explicit_permission=True, protected=True)
        with self.assertRaises(ReceiverBusy):
            self.bridge.start_fm_rds(
                owner_id="owner", receiver_id="rtl-A",
                frequency_hz=98_600_000, duration_seconds=20, user_triggered=True)
        self.assertEqual(self.broker.active("rtl-A")["app_id"], "flight_radar")
        self.assertTrue(self.broker.active("rtl-A")["protected"])
        self.assertEqual(self.guard.released, 1)
        self.assertFalse(self.backend.started)
        self.broker.release(lease.token, owner_id="owner")

    def test_owned_capture_stop_waits_for_decoder_ack(self):
        session = self.bridge.start_fm_rds(
            owner_id="owner", receiver_id="rtl-A", frequency_hz=98_600_000,
            duration_seconds=30, user_triggered=True)
        self.assertEqual(self.broker.active("rtl-A")["app_id"], "text_center")
        self.assertEqual(len(self.bridge.sessions(owner_id="owner")), 1)
        self.assertEqual(self.bridge.sessions(owner_id="other"), [])
        with self.assertRaises(PermissionError):
            self.bridge.stop_fm_rds(session.id, owner_id="other")
        self.backend.ack = False
        self.assertFalse(self.bridge.stop_fm_rds(session.id, owner_id="owner"))
        self.assertEqual(self.broker.active("rtl-A")["state"], "occupied")
        self.backend.ack = True
        self.assertTrue(self.bridge.stop_fm_rds(session.id, owner_id="owner"))
        self.assertEqual(self.broker.active("rtl-A")["state"], "free")
        self.assertEqual(self.guard.released, 1)

    def test_decoder_start_error_releases_all_resources(self):
        def broken(**kwargs): raise RuntimeError("rtl_fm missing")
        self.backend.start = broken
        with self.assertRaises(RuntimeError):
            self.bridge.start_fm_rds(
                owner_id="owner", receiver_id="rtl-A",
                frequency_hz=98_600_000, duration_seconds=20, user_triggered=True)
        self.assertEqual(self.broker.active("rtl-A")["state"], "free")
        self.assertEqual(self.guard.released, 1)


if __name__ == "__main__":
    unittest.main()
