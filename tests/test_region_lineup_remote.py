# SPDX-License-Identifier: AGPL-3.0-only
"""Regional channel candidates and phone-remote policy: no real RF hardware."""
import tempfile
import unittest
from pathlib import Path

from tihulu_runtime.channel_explorer import (
    DetectedService, ProbeReading, Receiver,
)
from tihulu_runtime.region_channel_manager import (
    ChannelLineupStore, RegionChannelCatalog,
)
from tihulu_runtime.remote_control import (
    RemoteCommandPolicy, RemoteTarget,
)

ROOT = Path(__file__).parents[1]
DATA = ROOT / "data"


class TestRegionChannelCatalog(unittest.TestCase):
    def setUp(self):
        self.catalog = RegionChannelCatalog(
            DATA / "region_profiles.json",
            DATA / "region_channel_catalog.json",
            DATA / "channel_frequency_presets.json",
        )

    def test_regions_cities_and_no_invented_city_coverage(self):
        self.assertEqual(len(self.catalog.regions["DE"]), 16)
        self.assertEqual(len(self.catalog.regions["TR"]), 81)
        self.assertIn("Köln", self.catalog.cities("DE","Nordrhein-Westfalen"))
        self.assertIn("İzmir Merkez", self.catalog.cities("TR","İzmir"))
        self.assertEqual(self.catalog.candidates("TR","Ankara","Ankara"), ())
        self.assertEqual(
            [x.id for x in self.catalog.candidates("TR","İzmir","İzmir Merkez")],
            ["tr_izmir_radyo1","tr_izmir_trtfm","tr_izmir_radyo3",
             "tr_izmir_radyohaber"])
        with self.assertRaises(ValueError):
            self.catalog.candidates("TR","Nonexistent","Istanbul")

    def test_koeln_has_tv_and_separate_radio_candidates(self):
        entries = self.catalog.candidates("DE","Nordrhein-Westfalen","Köln")
        keys = [p.id for p in entries]
        for name in ("de_nrw_koeln_wdr_tv","de_nrw_wdr_dab_11d",
                     "de_national_dab_5c","de_koeln_wdr2_fm"):
            self.assertIn(name,keys)
        self.assertEqual(len(keys),len(set(keys)))
        self.assertEqual(entries[0].frequency_hz,514000000)
        self.assertTrue(all(p.source.startswith("https://") for p in entries))
        self.assertNotIn("de_nrw_duesseldorf_wdr_tv",keys)
        with self.assertRaises(ValueError):
            self.catalog.eligible_preset("TR","İzmir","İzmir Merkez",
                                         "de_nrw_koeln_wdr_tv")

    def test_remote_catalog_requires_consented_registered_pack(self):
        with self.assertRaises(PermissionError):
            self.catalog.install_pack("any-pack",user_triggered=False)
        with self.assertRaises(KeyError):
            self.catalog.install_pack("not-offered",user_triggered=True)


class TestLineups(unittest.TestCase):
    def setUp(self):
        self.catalog=RegionChannelCatalog(
            DATA/"region_profiles.json",DATA/"region_channel_catalog.json",
            DATA/"channel_frequency_presets.json")
        self.tmp=tempfile.TemporaryDirectory()
        self.dbfile=Path(self.tmp.name)/"lineups.sqlite"
        self.store=ChannelLineupStore(self.dbfile,self.catalog)
        self.alice=self.store.create(owner_id="alice",country="DE",
              region="Nordrhein-Westfalen",city="Köln",label="Köln selection")
        self.bob=self.store.create(owner_id="bob",country="TR",
              region="İzmir",city="İzmir Merkez",label="İzmir selection")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_checkbox_selection_idempotence_and_owner_privacy(self):
        selected=self.store.add_presets(owner_id="alice",profile_id=self.alice,
             preset_ids=["de_nrw_koeln_wdr_tv","de_koeln_wdr2_fm",
                         "de_nrw_wdr_dab_11d"])
        self.assertEqual(len(selected),3)
        self.assertEqual(self.store.add_presets(owner_id="alice",
             profile_id=self.alice,preset_ids=["de_koeln_wdr2_fm"]),[])
        rows=self.store.items(owner_id="alice",profile_id=self.alice)
        self.assertEqual([r["position"] for r in rows],[0,1,2])
        self.assertEqual(rows[0]["state"],"published_not_received")
        self.assertEqual(len(self.store.items(owner_id="alice",
             profile_id=self.alice,media="radio")),2)
        self.assertEqual(len(self.store.items(owner_id="alice",
             profile_id=self.alice,media="tv")),1)
        with self.assertRaises(KeyError):
            self.store.items(owner_id="bob",profile_id=self.alice)
        with self.assertRaises(ValueError):
            self.store.add_presets(owner_id="alice",profile_id=self.alice,
                                   preset_ids=["tr_izmir_radyo1"])

    def test_custom_channel_edit_order_remove_persist(self):
        self.store.add_presets(owner_id="alice",profile_id=self.alice,
                               preset_ids=["de_nrw_koeln_wdr_tv"])
        custom=self.store.add_custom(owner_id="alice",profile_id=self.alice,
                         label="my FM",mode="fm",frequency_hz=99000000)
        rows=self.store.items(owner_id="alice",profile_id=self.alice)
        self.store.reorder(owner_id="alice",profile_id=self.alice,
                           item_ids=[custom,rows[0]["item_id"]])
        self.assertEqual(self.store.items(owner_id="alice",
            profile_id=self.alice)[0]["item_id"],custom)
        self.store.edit(owner_id="alice",profile_id=self.alice,item_id=custom,
                         label="changed FM",mode="fm",frequency_hz=98600000,
                         offset_hz=1000)
        changed=self.store.items(owner_id="alice",profile_id=self.alice)[0]
        self.assertEqual(changed["frequency_hz"],98600000)
        self.assertEqual(changed["state"],"manual_unverified")
        self.assertEqual(changed["offset_hz"],1000)
        with self.assertRaises(ValueError):
            self.store.reorder(owner_id="alice",profile_id=self.alice,
                               item_ids=[custom,custom])
        with self.assertRaises(KeyError):
            self.store.remove(owner_id="bob",profile_id=self.alice,
                              item_ids=[custom])
        self.store.close()
        self.store=ChannelLineupStore(self.dbfile,self.catalog)
        self.assertEqual(len(self.store.items(owner_id="alice",
                             profile_id=self.alice)),2)
        self.store.remove(owner_id="alice",profile_id=self.alice,
                          item_ids=[custom])
        self.assertEqual(len(self.store.items(owner_id="alice",
                             profile_id=self.alice)),1)

    def test_manual_tuning_needs_explicit_consent_and_respects_recording(self):
        [item]=self.store.add_presets(owner_id="alice",profile_id=self.alice,
                                      preset_ids=["de_nrw_koeln_wdr_tv"])
        receiver=Receiver("dvb0","dvb_tuner",frozenset({"dvb_t2"}),
                 470000000,690000000,connected=True,
                 locked_frequency_hz=530000000,recording_active=True)
        class NeverCalled:
            def probe(self,*_):
                raise AssertionError("Active recording must not retune")
        with self.assertRaises(PermissionError):
            self.store.tune_item(owner_id="alice",profile_id=self.alice,
                                 item_id=item,receiver=receiver)
        answer=self.store.tune_item(owner_id="alice",profile_id=self.alice,
                       item_id=item,receiver=receiver,user_triggered=True,
                       backend=NeverCalled())
        self.assertEqual(answer.state,"recording_protected")

    def test_invalid_custom_and_unknown_owner_cannot_mutate(self):
        with self.assertRaises(ValueError):
            self.store.add_custom(owner_id="alice",profile_id=self.alice,
                 label="bad",mode="fm",frequency_hz=0)
        with self.assertRaises(KeyError):
            self.store.edit(owner_id="bob",profile_id=self.alice,
                 item_id="fake",label="bad",mode="fm",frequency_hz=97000000)


class FakeTuner:
    def __init__(self):
        self.calls = 0
    def probe(self,receiver,point):
        self.calls += 1
        return ProbeReading("service_decoded",80,
                   (DetectedService("tv","Sample measured test mux","tv"),))


class FakeRenderer:
    def __init__(self):
        self.calls=[]
        self.ok=True
    def execute(self,target,command,*,item,value):
        self.calls.append((target.target_id,command,
                           None if item is None else item["label"],value))
        return self.ok


class TestRemotePolicy(unittest.TestCase):
    def setUp(self):
        self.catalog=RegionChannelCatalog(
            DATA/"region_profiles.json",DATA/"region_channel_catalog.json",
            DATA/"channel_frequency_presets.json")
        self.store=ChannelLineupStore(":memory:",self.catalog)
        self.profile=self.store.create(owner_id="alice",country="DE",
            region="Nordrhein-Westfalen",city="Köln",label="home")
        self.items=self.store.add_presets(owner_id="alice",profile_id=self.profile,
            preset_ids=["de_nrw_koeln_wdr_tv"])
        self.tuner=Receiver("dvb","dvb_tuner",frozenset({"dvb_t2"}),
                            470000000,690000000,connected=True)
        self.policy=RemoteCommandPolicy(self.store)
        self.target=RemoteTarget("alice","computer-tv","tv",connected=True)
        self.policy.register_target(self.target,trusted_server=True)
        self.renderer=FakeRenderer()
        self.backend=FakeTuner()

    def tearDown(self):
        self.store.close()

    def _send(self,**kwargs):
        return self.policy.command(owner_id="alice",paired_owner_id="alice",
           target_id="computer-tv",action="select_channel",user_triggered=True,
           profile_id=self.profile,item_id=self.items[0],
           receiver=self.tuner,tuner_backend=self.backend,
           renderer=self.renderer,**kwargs)

    def test_requires_registered_trusted_target_and_correct_pair(self):
        with self.assertRaises(PermissionError):
            self.policy.register_target(RemoteTarget("alice","bad","tv",True))
        with self.assertRaises(PermissionError):
            self.policy.command(owner_id="bob",paired_owner_id="bob",
                   target_id="computer-tv",action="mute",user_triggered=True,
                   renderer=self.renderer)
        with self.assertRaises(PermissionError):
            self.policy.command(owner_id="alice",paired_owner_id="bob",
                   target_id="computer-tv",action="mute",user_triggered=True,
                   renderer=self.renderer)
        with self.assertRaises(PermissionError):
            self.policy.command(owner_id="alice",paired_owner_id="alice",
                   target_id="computer-tv",action="mute",renderer=self.renderer)
        self.assertEqual(self.renderer.calls,[])

    def test_remote_requires_real_backend_acknowledgment(self):
        result=self.policy.command(owner_id="alice",paired_owner_id="alice",
            target_id="computer-tv",action="select_channel",user_triggered=True,
            profile_id=self.profile,item_id=self.items[0],
            receiver=self.tuner,renderer=self.renderer)
        self.assertEqual(result.status,"backend_missing")
        self.assertEqual(self.renderer.calls,[])
        self.renderer.ok=False
        result=self._send()
        self.assertEqual(result.status,"not_acknowledged")
        self.renderer.ok=True
        result=self._send()
        self.assertEqual(result.status,"acknowledged")
        self.assertEqual(len(self.renderer.calls),2)
        self.assertEqual(self.backend.calls,2)

    def test_ai_translator_are_not_fake_renderer_calls(self):
        for action in ("translate","ask_ai"):
            r=self.policy.command(owner_id="alice",paired_owner_id="alice",
               target_id="computer-tv",action=action,user_triggered=True,
               renderer=self.renderer)
            self.assertEqual(r.status,"integration_missing")
        self.assertEqual(self.renderer.calls,[])

    def test_no_unrestricted_commands_and_recording_safe_remote(self):
        with self.assertRaises(ValueError):
            self.policy.command(owner_id="alice",paired_owner_id="alice",
               target_id="computer-tv",action="run_shell",user_triggered=True,
               renderer=self.renderer)
        recording=Receiver("dvb","dvb_tuner",frozenset({"dvb_t2"}),
                 470000000,690000000,connected=True,
                 locked_frequency_hz=530000000,recording_active=True)
        r=self.policy.command(owner_id="alice",paired_owner_id="alice",
            target_id="computer-tv",action="select_channel",user_triggered=True,
            profile_id=self.profile,item_id=self.items[0],receiver=recording,
            tuner_backend=self.backend,renderer=self.renderer)
        self.assertEqual(r.status,"recording_protected")
        self.assertEqual(self.backend.calls,0)
        self.assertEqual(self.renderer.calls,[])


if __name__ == "__main__":
    unittest.main()
