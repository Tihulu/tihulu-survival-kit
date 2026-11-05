# SPDX-License-Identifier: AGPL-3.0-only
import unittest
from tihulu_runtime.linux_dvb_backend import LinuxDvbV5Backend
from tihulu_runtime.channel_explorer import Receiver, TunePoint

class LinuxDvbBackendTests(unittest.TestCase):
    def test_generates_explicit_single_dvbt2_frequency(self):
        x=LinuxDvbV5Backend.scan_input(TunePoint("dvb_t2",514000000,8000000))
        self.assertIn("DELIVERY_SYSTEM = DVBT2",x)
        self.assertIn("FREQUENCY = 514000000",x)
        self.assertNotIn("SYMBOL_RATE",x)

    def test_no_dvbc_without_actual_symbol_rate(self):
        with self.assertRaises(NotImplementedError):
            LinuxDvbV5Backend.scan_input(TunePoint("dvb_c",514000000))

    def test_parse_actual_scanner_like_channel_file_without_faking_teletext(self):
        sample="""[WDR Koeln HD]
SERVICE_ID = 43
VIDEO_PID = 202
AUDIO_PID = 203
DELIVERY_SYSTEM = DVBT2
FREQUENCY = 514000000
BANDWIDTH_HZ = 8000000

[Digital Radio Test]
SERVICE_ID = 44
AUDIO_PID = 301
DELIVERY_SYSTEM = DVBT2
FREQUENCY = 514000000

[Other Multiplex]
SERVICE_ID = 79
VIDEO_PID = 802
FREQUENCY = 530000000
"""
        result=LinuxDvbV5Backend.parse_channel_config(sample,frequency_hz=514000000)
        self.assertEqual(len(result),2)
        self.assertEqual(result[0].content_kind,"tv")
        self.assertEqual(result[1].content_kind,"radio")
        self.assertNotIn("Other Multiplex",[x.label for x in result])

    def test_live_recording_blocks_direct_scanner_invocation(self):
        receiver=Receiver("dvb0","dvb_tuner",frozenset({"dvb_t2"}),
                          470000000,690000000,connected=True,
                          locked_frequency_hz=514000000,
                          recording_active=True,share_locked_mux=True)
        with self.assertRaisesRegex(RuntimeError, "recording is active"):
            LinuxDvbV5Backend().probe(receiver,TunePoint("dvb_t2",514000000))

    def test_missing_receiver_cannot_run_scanner(self):
        receiver=Receiver("dvb0","dvb_tuner",frozenset({"dvb_t2"}),
                          470000000,690000000,connected=False)
        with self.assertRaisesRegex(RuntimeError, "Receiver unavailable"):
            LinuxDvbV5Backend().probe(receiver,TunePoint("dvb_t2",514000000))

    def test_rejects_excessive_input_or_fake_device_parameter(self):
        with self.assertRaises(ValueError):
            LinuxDvbV5Backend(adapter_index=-1)
        with self.assertRaises(ValueError):
            LinuxDvbV5Backend(binary="bash")
        with self.assertRaises(ValueError):
            LinuxDvbV5Backend.scan_input(TunePoint("dvb_t2",514000000,5000000))
        with self.assertRaises(ValueError):
            LinuxDvbV5Backend.parse_channel_config("a"*2000001,
                                                      frequency_hz=514000000)

if __name__=="__main__":
    unittest.main()
