"""Validate source catalog does not invent capabilities of DVB receiver."""
import json
import unittest
from pathlib import Path


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parents[1] / "data" / "radio_text_networks.json"
        cls.data = json.loads(path.read_text(encoding="utf-8"))

    def test_tv_is_receive_only(self):
        d = self.data["devices"]["wintv_solohd_01589"]
        self.assertTrue(d["receive_only"])
        self.assertEqual(set(d["supported_receivers"]), {"dvb_t", "dvb_t2", "dvb_c"})

    def test_no_broadcast_text_is_marked_transmit(self):
        for source in self.data["services"]:
            if source["hardware"] == "wintv_solohd_01589":
                self.assertNotIn(source["mode"], ("transmit", "two_way_conditional"))

    def test_bidirectional_requires_other_hardware(self):
        for source in self.data["services"]:
            if source["mode"] == "two_way_conditional":
                self.assertIn(source["hardware"], ("meshtastic_optional", "packet_radio_optional"))
                self.assertTrue(source.get("source_url", "").startswith("https://"))

    def test_actual_lora_regions_not_pretended_universal(self):
        services = {s["id"]: s for s in self.data["services"]}
        self.assertEqual(services["mesh_rheinland"]["country"], "DE")
        self.assertEqual(services["trt_telegun"]["country"], "TR")
        self.assertFalse(self.data["defaults"]["network_transmission"])
        self.assertFalse(self.data["defaults"]["teletext_capture_background"])

    def test_no_service_claims_successful_signal_capture(self):
        for source in self.data["services"]:
            self.assertFalse(source.get("received_now", False))


if __name__ == "__main__":
    unittest.main()
