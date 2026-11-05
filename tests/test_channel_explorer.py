# SPDX-License-Identifier: AGPL-3.0-only
import tempfile
import unittest
from pathlib import Path

from tihulu_runtime.channel_explorer import (
    ChannelExplorer, ChannelStore, DetectedService, FrequencyLibrary,
    ProbeReading, Receiver, ScanRecord, TunePoint,
)


DATA = Path(__file__).parents[1] / "data" / "channel_frequency_presets.json"


class FakeReceiver:
    def __init__(self):
        self.probed = []
    def probe(self, receiver, point):
        self.probed.append((receiver.receiver_id, point.tuned_hz))
        if point.frequency_hz == 514000000:
            return ProbeReading("service_decoded", 84.0,
                (DetectedService("wdr-hd","WDR HD Köln","tv"),))
        if point.frequency_hz == 98600000:
            return ProbeReading("signal_locked", 60)
        return ProbeReading("no_signal")


class ChannelExplorerTests(unittest.TestCase):
    def setUp(self):
        self.library = FrequencyLibrary.from_json(DATA)
        self.exp = ChannelExplorer()
        self.dvb = Receiver("tuner0", "dvb_tuner", frozenset({"dvb_t2","dvb_t","dvb_c"}),
                            470000000, 690000000, connected=True,
                            fine_tune_supported=True)
        self.sdr = Receiver("sdr0","radio_sdr",frozenset({"fm","dab","nfm"}),
                            24000000, 1700000000, connected=True)
        self.backend = FakeReceiver()

    def test_verified_seed_known_sources_and_unverified_rf(self):
        self.assertGreaterEqual(len(self.library.presets), 12)
        wdr=self.library.presets["de_nrw_koeln_wdr_tv"]
        self.assertEqual(wdr.frequency_hz,514000000)
        self.assertEqual(wdr.kind,"dvb_t2")
        self.assertTrue(wdr.source.startswith("https://"))
        self.assertEqual(self.library.presets["tr_izmir_radyo1"].frequency_hz,94700000)

    def test_full_dab_raster_uses_nonuniform_channel_spacing(self):
        points=self.library.channel_group_points("dab_band_iii")
        self.assertEqual(len(points),32)
        self.assertEqual(points[0].frequency_hz,174928000)
        self.assertEqual(points[2].frequency_hz,178352000)
        self.assertEqual(points[16].frequency_hz,202928000)
        self.assertEqual(points[27].frequency_hz,222064000)
        self.assertEqual(points[-1].frequency_hz,229072000)
        self.assertNotEqual(points[4].frequency_hz-points[3].frequency_hz,
                            points[3].frequency_hz-points[2].frequency_hz)

    def test_no_implicit_scan_and_missing_receiver(self):
        with self.assertRaises(PermissionError):
            self.exp.scan(self.dvb,(TunePoint("dvb_t2",514000000),),backend=self.backend)
        missing=Receiver("unconnected","dvb_tuner",frozenset({"dvb_t2"}),
                         470000000,690000000,connected=False)
        r=self.exp.scan(missing,(TunePoint("dvb_t2",514000000),),
                         user_triggered=True,backend=self.backend)
        self.assertEqual(r[0].state,"hardware_missing")
        self.assertFalse(self.backend.probed)

    def test_simultaneous_physical_receivers_only_on_supported_bands(self):
        r=self.exp.scan(self.dvb,(TunePoint("fm",98600000),),user_triggered=True,
                         backend=self.backend)
        self.assertEqual(r[0].state,"hardware_missing")
        q=self.exp.scan(self.sdr,(TunePoint("fm",98600000),),user_triggered=True,
                         backend=self.backend)
        self.assertEqual(q[0].state,"signal_locked")

    def test_two_scanned_channels_sorted_by_signal_evidence(self):
        plans=(TunePoint("dvb_t2",522000000),TunePoint("dvb_t2",514000000))
        out=self.exp.scan(self.dvb,plans,user_triggered=True,backend=self.backend)
        result=self.exp.sort_discovered(out)
        self.assertEqual(result[0].frequency_hz,514000000)
        self.assertEqual(result[0].state,"service_decoded")
        self.assertEqual(result[0].services[0].label,"WDR HD Köln")

    def test_wide_band_is_chunked_and_does_not_auto_stream(self):
        p=self.library.band_points("de_amateur_70cm",page=0,page_size=32)
        self.assertEqual(len(p),32)
        self.assertEqual(p[0].frequency_hz,430000000)
        self.assertEqual(p[1].frequency_hz,430025000)
        with self.assertRaises(ValueError):
            self.library.band_points("de_amateur_70cm",page_size=500)
        self.assertFalse(self.library.band_points("de_fm_87_5_108",page=999))
        with self.assertRaises(ValueError):
            self.exp.scan(self.sdr,tuple(TunePoint("fm",90000000) for i in range(257)),
                          user_triggered=True)

    def test_recording_never_retuned_even_for_tuner_fine_adjustment(self):
        locked=Receiver("tuner0","dvb_tuner",frozenset({"dvb_t2"}),
                        470000000,690000000,True,
                        locked_frequency_hz=514000000,recording_active=True,
                        fine_tune_supported=True)
        r=self.exp.manual_tune(locked,mode="dvb_t2",frequency_hz=514000000,
             fine_offset_hz=25000,user_triggered=True,backend=self.backend)
        self.assertEqual(r.state,"recording_protected")
        self.assertFalse(self.backend.probed)

    def test_same_mux_requires_separate_non_retuning_backend(self):
        locked=Receiver("tuner0","dvb_tuner",frozenset({"dvb_t2"}),
                        470000000,690000000,True,
                        locked_frequency_hz=514000000,recording_active=True,
                        share_locked_mux=True)
        # A scanner with only probe() must not run even at the same frequency.
        blocked=self.exp.manual_tune(locked,mode="dvb_t2",frequency_hz=514000000,
                                     user_triggered=True,backend=self.backend)
        self.assertEqual(blocked.state,"recording_protected")
        self.assertFalse(self.backend.probed)

        class SharedMuxReader(FakeReceiver):
            def __init__(self):
                super().__init__()
                self.reads=[]
            def probe_shared_mux(self, receiver, point):
                self.reads.append((receiver.receiver_id, point.tuned_hz))
                return ProbeReading("service_decoded", 84,
                    (DetectedService("wdr-hd","WDR HD Köln","tv"),))
        reader=SharedMuxReader()
        out=self.exp.manual_tune(locked,mode="dvb_t2",frequency_hz=514000000,
                                 user_triggered=True,backend=reader)
        self.assertEqual(out.state,"service_decoded")
        self.assertEqual(reader.reads,[("tuner0",514000000)])
        self.assertFalse(reader.probed)  # A regular retuning probe never runs.

        shifted=self.exp.manual_tune(locked,mode="dvb_t2",frequency_hz=513975000,
                   fine_offset_hz=25000,user_triggered=True,backend=reader)
        self.assertEqual(shifted.state,"recording_protected")
        other=self.exp.manual_tune(locked,mode="dvb_t2",frequency_hz=522000000,
                                   user_triggered=True,backend=reader)
        self.assertEqual(other.state,"recording_protected")
        self.assertEqual(len(reader.reads),1)

    def test_fine_tune_requires_receiver_capability_and_bounded_offset(self):
        a=self.exp.manual_tune(self.sdr,mode="fm",frequency_hz=98600000,
                               fine_offset_hz=10000,user_triggered=True,
                               backend=self.backend)
        self.assertEqual(a.state,"hardware_missing")
        with self.assertRaises(ValueError):
            self.exp.manual_tune(self.dvb,mode="dvb_t2",frequency_hz=514000000,
                                 fine_offset_hz=750000,user_triggered=True)

    def test_no_backend_means_no_fake_lock(self):
        r=self.exp.manual_tune(self.dvb,mode="dvb_t2",frequency_hz=514000000,
                               user_triggered=True)
        self.assertEqual(r.state,"backend_missing")

    def test_stored_channel_is_owner_scoped_and_user_data_survives_news_purge(self):
        record=ScanRecord("tuner0","dvb_t2",514000000,"service_decoded",
                          (DetectedService("1","WDR","tv"),),72.0)
        with tempfile.TemporaryDirectory() as tmp:
            store=ChannelStore(Path(tmp)/"channels.sqlite")
            key=store.save(owner_id="alice",record=record,service=record.services[0],
                           favorite=True)
            self.assertEqual(store.list(owner_id="bob"),[])
            self.assertEqual(len(store.list(owner_id="alice",only_favorites=True)),1)
            with self.assertRaises(KeyError):
                store.set_favorite(key,owner_id="bob",favorite=False)
            store.close()
            again=ChannelStore(Path(tmp)/"channels.sqlite")
            self.assertEqual(again.list(owner_id="alice")[0]["label"],"WDR")
            again.remove(key,owner_id="alice")
            self.assertEqual(again.list(owner_id="alice"),[])
            again.close()

    def test_unclassified_energy_not_labelled_as_station(self):
        record=ScanRecord("sdr0","nfm",144500000,"energy_only",(),42.0)
        with tempfile.TemporaryDirectory() as tmp:
            store=ChannelStore(Path(tmp)/"db.sqlite")
            store.save(owner_id="alice",record=record)
            item=store.list(owner_id="alice")[0]
            self.assertEqual(item["state"],"energy_only")
            self.assertEqual(item["label"],"Unclassified signal")
            with self.assertRaises(ValueError):
                store.save(owner_id="alice",record=ScanRecord(
                    "sdr0","nfm",144500000,"backend_missing"))
            store.close()

    def test_tuner_rejects_arbitrary_services_without_provenance(self):
        class FakeBad:
            def probe(self,receiver,point):
                return ProbeReading("energy_only",77,
                                    (DetectedService("x","Fake TV","tv"),))
        out=self.exp.scan(self.dvb,(TunePoint("dvb_t2",514000000),),
                          user_triggered=True,backend=FakeBad())
        self.assertEqual(out[0].state,"scan_failed")


if __name__=="__main__":
    unittest.main()
