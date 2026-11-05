# SPDX-License-Identifier: AGPL-3.0-only
import unittest
from pathlib import Path
from tihulu_runtime.channel_app_registry import SharedChannelWorkspace
from tihulu_runtime.channel_explorer import (
    ChannelStore, FrequencyLibrary, Receiver, ScanRecord, DetectedService
)

DATA=Path(__file__).parents[1]/"data"/"channel_frequency_presets.json"

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.store=ChannelStore(":memory:")
        self.workspace=SharedChannelWorkspace(FrequencyLibrary.from_json(DATA),self.store)
        self.dvb=Receiver("dvb","dvb_tuner",frozenset({"dvb_t2"}),
                          470000000,690000000,connected=True)
        self.sdr=Receiver("sdr","radio_sdr",frozenset({"fm","dab","nfm"}),
                          24000000,1700000000,connected=True)

    def tearDown(self):
        self.store.close()

    def test_published_presets_are_shared_but_not_received(self):
        self.assertTrue(self.workspace.presets(country="DE",app="tv"))
        self.assertTrue(self.workspace.presets(country="TR",app="radio"))
        self.assertEqual(self.workspace.saved(owner_id="alice"),[])

    def test_tv_radio_split_including_dvb_audio_only(self):
        record=ScanRecord("dvb","dvb_t2",514000000,"service_decoded",(
            DetectedService("v1","WDR TV","tv"),
            DetectedService("r1","DVB Radio","radio")),80)
        for service in record.services:
            self.store.save(owner_id="alice",record=record,service=service)
        self.assertEqual(len(self.workspace.saved(owner_id="alice",app="tv")),1)
        self.assertEqual(len(self.workspace.saved(owner_id="alice",app="radio")),1)
        self.assertEqual(len(self.workspace.saved(owner_id="bob",app="all")),0)

    def test_manual_candidate_is_not_a_confirmed_broadcast(self):
        self.store.save_manual(owner_id="alice",receiver_id="sdr",mode="nfm",
                               frequency_hz=144500000,label="My unknown signal")
        row=self.workspace.saved(owner_id="alice",app="radio")[0]
        self.assertEqual(row["state"],"manual_unverified")
        self.assertEqual(row["source"],"user_entry")

    def test_tuning_saved_dvb_needs_explicit_action(self):
        key=self.store.save_manual(owner_id="alice",receiver_id="dvb",mode="dvb_t2",
                                    frequency_hz=514000000,label="WDR trial")
        with self.assertRaises(PermissionError):
            self.workspace.tune_saved(owner_id="alice",channel_key=key,receiver=self.dvb)
        with self.assertRaises(KeyError):
            self.workspace.tune_saved(owner_id="bob",channel_key=key,
                                       receiver=self.dvb,user_triggered=True)
        result=self.workspace.tune_saved(owner_id="alice",channel_key=key,
                                         receiver=self.dvb,user_triggered=True)
        self.assertEqual(result.state,"backend_missing")

    def test_app_will_not_sweep_wrong_receiver_mode(self):
        with self.assertRaises(ValueError):
            self.workspace.scan_presets(owner_id="alice",app="tv",
                preset_ids=["tr_izmir_radyo1"],receiver=self.sdr,user_triggered=True)
        result=self.workspace.scan_presets(owner_id="alice",app="radio",
                preset_ids=["tr_izmir_radyo1"],receiver=self.sdr,user_triggered=True)
        self.assertEqual(result[0].state,"backend_missing")

    def test_receiver_scan_does_not_auto_save_when_disabled(self):
        results=self.workspace.scan_presets(owner_id="alice",app="tv",
             preset_ids=["de_nrw_koeln_wdr_tv"],receiver=self.dvb,
             user_triggered=True,save_discoveries=True)
        self.assertEqual(results[0].state,"backend_missing")
        self.assertFalse(self.workspace.saved(owner_id="alice"))

if __name__=="__main__":
    unittest.main()
