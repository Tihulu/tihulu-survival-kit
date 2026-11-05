# SPDX-License-Identifier: AGPL-3.0-only
import unittest
from tihulu_runtime.signal_explorer import (
    SignalExplorer, ScanPlan, ScanDenied, ReceiverState, Observation, Preset
)

class FakeReceiver:
    def __init__(self):
        self.probes=[];self.tunes=[]
    def observe(self, *, mode,frequency_hz,bandwidth_hz):
        self.probes.append(frequency_hz)
        return Observation(frequency_hz,mode,frequency_hz==514000000,
                           ("WDR Television",) if frequency_hz==514000000 else (),
                           ("teletext","epg") if frequency_hz==514000000 else (),
                           -48.0 if frequency_hz==514000000 else None,
                           original_locator="mocked transport PID")
    def tune(self, *, mode,frequency_hz,bandwidth_hz):
        self.tunes.append(frequency_hz)

class ExplorerTests(unittest.TestCase):
    def setUp(self):
        self.x=SignalExplorer()
        self.r=FakeReceiver()
        self.state=ReceiverState("tv001",True,frozenset({"dvb_t2"}))
    def test_explicit_frequency_sweep_and_saved_result(self):
        plan=self.x.sweep("dvb_t2",start_hz=506000000,stop_hz=522000000,
                          step_hz=8000000,bandwidth_hz=8000000,owner_requested=True)
        found=self.x.scan(plan,self.state,self.r)
        self.assertEqual(self.r.probes,[506000000,514000000,522000000])
        self.assertEqual(len(found),1)
        self.assertEqual(found[0].service_name,"WDR Television")
        self.x.favorite(found[0].id)
        self.x.tune(found[0].id,state=self.state,receiver=self.r,owner_requested=True)
        self.assertEqual(self.r.tunes,[514000000])
    def test_no_implicit_scan_or_tune(self):
        p=self.x.sweep("dvb_t2",start_hz=514000000,stop_hz=514000000,step_hz=8000000)
        with self.assertRaises(ScanDenied):self.x.scan(p,self.state,self.r)
        self.assertEqual(self.r.probes,[])
    def test_recording_cannot_be_retuned(self):
        p=self.x.sweep("dvb_t2",start_hz=506000000,stop_hz=522000000,
                       step_hz=8000000,owner_requested=True)
        state=ReceiverState("tv001",True,frozenset({"dvb_t2"}),514000000,True,True)
        with self.assertRaises(ScanDenied):self.x.scan(p,state,self.r)
        p2=self.x.sweep("dvb_t2",start_hz=514000000,stop_hz=514000000,
                        step_hz=8000000,owner_requested=True)
        self.assertEqual(len(self.x.scan(p2,state,self.r)),1)
    def test_tv_tuner_cannot_scan_radio(self):
        p=self.x.sweep("dab_plus",start_hz=222064000,stop_hz=222064000,
                       step_hz=1000,owner_requested=True)
        with self.assertRaises(ScanDenied):self.x.scan(p,self.state,self.r)
    def test_limit_and_frequency_validation(self):
        with self.assertRaises(ValueError):
            self.x.sweep("fm",start_hz=87500000,stop_hz=108000000,step_hz=1000)
        with self.assertRaises(ValueError):
            self.x.sweep("fm",start_hz=40000000,stop_hz=108000000,step_hz=1000000)
    def test_tune_requires_known_observed_station(self):
        with self.assertRaises(KeyError):
            self.x.tune("notfound",state=self.state,receiver=self.r,owner_requested=True)
    def test_unrecognized_carrier_not_invented_as_station(self):
        class Unknown:
            def observe(self,*,mode,frequency_hz,bandwidth_hz):
                return Observation(frequency_hz,mode,True)
        p=self.x.sweep("dvb_t2",start_hz=514000000,stop_hz=514000000,
                       step_hz=8000000,owner_requested=True)
        found=self.x.scan(p,self.state,Unknown())
        self.assertEqual(found[0].service_name,"Unknown signal")
    def test_no_transmission(self):
        p=ScanPlan("dvb_t2",(514000000,),owner_requested=True,transmit=True)
        with self.assertRaises(ScanDenied):self.x.scan(p,self.state,self.r)
    def test_preset_multiple_modulations(self):
        p=[Preset("wdr","WDR","DE","NRW","dvb_t2",514000000,8000000,"WDR"),
           Preset("fm","FM","DE","NRW","fm",91300000,None,"Deutschlandfunk")]
        plans=self.x.from_presets(p,owner_requested=True)
        self.assertEqual(len(plans),2)
        self.assertEqual({a.mode for a in plans},{"dvb_t2","fm"})
if __name__=="__main__":unittest.main()
