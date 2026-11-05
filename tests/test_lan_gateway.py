# SPDX-License-Identifier: AGPL-3.0-only
"""Self-contained local HTTP and pairing tests; no Pi tuner or internet use."""
import http.client
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path

from tihulu_runtime.lan_remote_broker import LanRemoteBroker
from tihulu_runtime.lan_remote_gateway import (
    RegionalLanGateway, GatewayError, build_server,
)

OWNER = "owner-token-for-unit-tests-0000000000000000001"
AUTH = {"Host":"localhost:8443", "Authorization":"Bearer "+OWNER}


class FakeClock:
    def __init__(self):
        self.value=1000
    def __call__(self):
        return self.value
    def forward(self,seconds):
        self.value+=seconds


class PairingBrokerTests(unittest.TestCase):
    def setUp(self):
        self.clock=FakeClock()
        self.broker=LanRemoteBroker(clock=self.clock)

    def test_one_time_code_and_ack_does_not_claim_media_success(self):
        display=self.broker.register(owner="alice",medium="tv")
        phone=self.broker.pair(display["pairing_code"],peer="192.0.2.20")
        with self.assertRaises(PermissionError):
            self.broker.pair(display["pairing_code"],peer="192.0.2.20")
        sent=self.broker.send(phone["remote_token"],action="volume_up")
        self.assertEqual(sent["state"],"pending")
        [delivered]=self.broker.poll(display["display_token"])
        self.assertEqual(delivered["command_id"],sent["command_id"])
        self.assertEqual(self.broker.poll(display["display_token"]),[])
        self.assertEqual(self.broker.status(phone["remote_token"],sent["command_id"])
                         ["state"],"delivered_unacknowledged")
        ack=self.broker.acknowledge(display["display_token"],sent["command_id"],
                                    accepted=True)
        self.assertEqual(ack["state"],"display_received")
        self.assertIn("no media playback",ack["detail"])
        with self.assertRaises(ValueError):
            self.broker.acknowledge(display["display_token"],sent["command_id"],
                                    accepted=True)

    def test_simultaneous_displays_never_share_an_active_pairing_code(self):
        with patch("tihulu_runtime.lan_remote_broker.secrets.randbelow",
                   side_effect=[42,42,43]):
            first=self.broker.register(owner="alice",medium="tv")
            second=self.broker.register(owner="alice",medium="tv")
        self.assertEqual(first["pairing_code"],"00000042")
        self.assertEqual(second["pairing_code"],"00000043")
        paired=self.broker.pair(second["pairing_code"],peer="second-phone")
        self.assertEqual(paired["target_id"],second["target_id"])

    def test_expiry_and_revocation(self):
        first=self.broker.register(owner="alice",medium="radio")
        self.clock.forward(121)
        with self.assertRaises(PermissionError):
            self.broker.pair(first["pairing_code"],peer="peer")
        other=self.broker.register(owner="alice",medium="tv")
        phone=self.broker.pair(other["pairing_code"],peer="peer2")
        with self.assertRaises(PermissionError):
            self.broker.revoke(owner="bob",target_id=other["target_id"])
        self.broker.revoke(owner="alice",target_id=other["target_id"])
        with self.assertRaises(PermissionError):
            self.broker.remote(phone["remote_token"])
        with self.assertRaises(PermissionError):
            self.broker.display(other["display_token"])
        expiring=self.broker.register(owner="alice",medium="tv")
        self.clock.forward(3601)
        with self.assertRaises(PermissionError):
            self.broker.display(expiring["display_token"])

    def test_bounded_bruteforce_and_commands(self):
        display=self.broker.register(owner="alice",medium="tv")
        for _ in range(5):
            with self.assertRaises(PermissionError):
                self.broker.pair("00000000",peer="scanner")
        with self.assertRaisesRegex(PermissionError,"rate limited"):
            self.broker.pair(display["pairing_code"],peer="scanner")
        phone=self.broker.pair(display["pairing_code"],peer="legitimate")
        with self.assertRaises(ValueError):
            self.broker.send(phone["remote_token"],action="run_shell")
        with self.assertRaises(ValueError):
            self.broker.send(phone["remote_token"],action="select_channel")
        sent=[self.broker.send(phone["remote_token"],action="mute")
              for _ in range(64)]
        self.assertEqual(len(sent),64)
        with self.assertRaises(ValueError):
            self.broker.send(phone["remote_token"],action="mute")
        self.assertEqual(len(self.broker.poll(display["display_token"])),32)
        # Expired undelivered commands must not accumulate for days if a
        # phone is paired but its display browser stopped polling.
        self.clock.forward(181)
        self.broker.send(phone["remote_token"],action="mute")
        self.assertEqual(len(self.broker._queues[display["target_id"]]),1)
        self.assertEqual(len(self.broker._commands),1)


class GatewayPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"shared.sqlite"
        self.gateway=RegionalLanGateway(self.path,owner_secret=OWNER)

    def tearDown(self):
        self.temp.cleanup()

    def call(self,method,path,body=None,token=OWNER,origin=None,host="localhost:8443"):
        headers={"Host":host}
        if token is not None:
            headers["Authorization"]="Bearer "+token
        if origin is not None:
            headers["Origin"]=origin
        return self.gateway.dispatch(method,path,headers,body,
                        peer="127.0.0.1",secure=False)

    def test_country_city_preset_and_persisted_owner_profile(self):
        status,data=self.call("GET","/api/regions")
        self.assertEqual(status,200)
        self.assertEqual(len(data["countries"]),2)
        _,cities=self.call("GET","/api/cities?country=DE&region=Nordrhein-Westfalen")
        self.assertIn("Köln",cities["cities"])
        _,candidates=self.call("GET",
            "/api/candidates?country=DE&region=Nordrhein-Westfalen&city=K%C3%B6ln")
        self.assertEqual(candidates["status"],"published_not_received")
        ids={x["id"] for x in candidates["candidates"]}
        self.assertIn("de_nrw_koeln_wdr_tv",ids)
        _,result=self.call("POST","/api/profiles",{
            "country":"DE","region":"Nordrhein-Westfalen",
            "city":"Köln","label":"Home"})
        profile=result["profile_id"]
        _,added=self.call("POST","/api/items/presets",{
            "profile_id":profile,
            "preset_ids":["de_nrw_koeln_wdr_tv","de_koeln_wdr2_fm"]})
        self.assertEqual(len(added["added_item_ids"]),2)
        _,items=self.call("GET","/api/items?profile_id="+profile)
        self.assertEqual(len(items["items"]),2)
        ids=[x["item_id"] for x in items["items"]]
        self.call("POST","/api/items/reorder",{"profile_id":profile,
                                                "item_ids":ids[::-1]})
        restarted=RegionalLanGateway(self.path,owner_secret=OWNER)
        status,found=restarted.dispatch("GET","/api/items?profile_id="+profile,
                     AUTH,peer="127.0.0.1")
        self.assertEqual(status,200)
        self.assertEqual([x["item_id"] for x in found["items"]],ids[::-1])

    def test_origin_host_and_authorization_rejected(self):
        with self.assertRaises(GatewayError) as e:
            self.call("GET","/api/profiles",token=None)
        self.assertEqual(e.exception.status,401)
        with self.assertRaises(GatewayError) as e:
            self.call("GET","/api/profiles",token="forged-secret")
        self.assertEqual(e.exception.status,403)
        with self.assertRaises(GatewayError) as e:
            self.call("POST","/api/profiles",{},origin="https://evil.example")
        self.assertEqual(e.exception.status,403)
        with self.assertRaises(GatewayError) as e:
            self.call("GET","/api/health",token=None,host="evil.example")
        self.assertEqual(e.exception.status,403)
        with self.assertRaises(GatewayError) as e:
            self.call("POST","/api/display/register",{"medium":"TV"})
        self.assertEqual(e.exception.status,422)

    def test_pairing_and_medium_limited_queue_not_tuner(self):
        _,created=self.call("POST","/api/profiles",{
            "country":"DE","region":"Nordrhein-Westfalen",
            "city":"Köln","label":"TV list"})
        profile=created["profile_id"]
        self.call("POST","/api/items/presets",{
            "profile_id":profile,
            "preset_ids":["de_nrw_koeln_wdr_tv","de_koeln_wdr2_fm"]})
        _,tv=self.call("GET","/api/items?profile_id="+profile+"&medium=tv")
        tv_item=tv["items"][0]["item_id"]
        _,registered=self.call("POST","/api/display/register",{"medium":"tv"})
        with self.assertRaises(GatewayError) as ex:
            self.call("POST","/api/remote/pair",
                {"code":registered["pairing_code"]},token=None,
                origin="https://malicious.example")
        self.assertEqual(ex.exception.status,403)
        _,paired=self.call("POST","/api/remote/pair",
                 {"code":registered["pairing_code"]},token=None)
        remote=paired["remote_token"]
        _,remote_items=self.call("GET",
            "/api/items?profile_id="+profile,token=remote)
        self.assertEqual(len(remote_items["items"]),1)
        with self.assertRaises(GatewayError) as e:
            self.call("POST","/api/items/custom",{
                "profile_id":profile,"label":"hack","mode":"fm",
                "frequency_hz":98600000},token=remote)
        self.assertEqual(e.exception.status,403)
        with self.assertRaises(GatewayError):
            self.call("POST","/api/remote/send",{
                "action":"select_channel","profile_id":profile,
                "item_id":"fake-radio"},token=remote)
        _,queued=self.call("POST","/api/remote/send",{
           "action":"select_channel","profile_id":profile,
           "item_id":tv_item},token=remote)
        self.assertEqual(queued["state"],"pending")
        _,pending=self.call("GET","/api/display/poll",
                             token=registered["display_token"])
        self.assertEqual(len(pending["commands"]),1)
        _,ack=self.call("POST","/api/display/ack",{
            "command_id":queued["command_id"],"accepted":True},
            token=registered["display_token"])
        self.assertEqual(ack["state"],"display_received")
        _,state=self.call("GET","/api/remote/status?command_id="+
                         queued["command_id"],token=remote)
        self.assertEqual(state["state"],"display_received")
        self.call("POST","/api/display/revoke",
                  {"target_id":registered["target_id"]})
        with self.assertRaises(GatewayError) as exc:
            self.call("GET","/api/profiles",token=remote)
        self.assertEqual(exc.exception.status,403)

    def test_no_nonloopback_without_tls(self):
        with self.assertRaisesRegex(ValueError,"requires TLS"):
            build_server("0.0.0.0",8443,self.gateway)
        with self.assertRaises(ValueError):
            RegionalLanGateway(self.path,owner_secret="short")
        with self.assertRaises(ValueError):
            RegionalLanGateway(self.path,owner_secret=OWNER,
                               allowed_hosts=("host/path",))


class LocalHttpGatewayTests(unittest.TestCase):
    """Real stdlib HTTP over loopback; no external network or RF hardware."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.gateway=RegionalLanGateway(Path(self.temp.name)/"http.sqlite",
                                        owner_secret=OWNER)
        self.server=build_server("127.0.0.1",0,self.gateway)
        self.port=self.server.server_address[1]
        self.worker=threading.Thread(target=self.server.serve_forever,
                                     daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.worker.join(timeout=3)
        self.server.server_close()
        self.temp.cleanup()

    def fetch(self,path,*,method="GET",body=None,token=None,
              headers=None):
        c=http.client.HTTPConnection("127.0.0.1",self.port,timeout=3)
        h={"Host":"localhost:"+str(self.port)}
        if token is not None:
            h["Authorization"]="Bearer "+token
        if body is not None:
            h["Content-Type"]="application/json"
            body=json.dumps(body)
        if headers:
            h.update(headers)
        c.request(method,path,body=body,headers=h)
        r=c.getresponse()
        raw=r.read()
        out=(r.status,raw,dict(r.getheaders()))
        c.close()
        return out

    def test_static_ui_health_auth_and_no_cache(self):
        status,html,headers=self.fetch("/")
        self.assertEqual(status,200)
        self.assertIn(b"B\xc3\xb6lgesel Kanallar",html)
        self.assertEqual(headers["Cache-Control"],"no-store")
        self.assertIn("frame-ancestors",headers["Content-Security-Policy"])
        status,js,_=self.fetch("/app.js")
        self.assertEqual(status,200)
        self.assertIn(b"remoteSend",js)
        status,data,_=self.fetch("/api/health")
        self.assertEqual(status,200)
        self.assertFalse(json.loads(data)["receiver_integrated"])
        status,_,_=self.fetch("/api/profiles")
        self.assertEqual(status,401)
        status,contents,_=self.fetch("/api/profiles",token=OWNER)
        self.assertEqual(status,200)
        self.assertEqual(json.loads(contents)["profiles"],[])

    def test_independent_http_clients_pair_relay_and_ack_without_media(self):
        # Each fetch uses its own HTTP client connection; display and remote
        # exchange data only through the server, never BroadcastChannel.
        status,body,_=self.fetch("/api/display/register",method="POST",
                    body={"medium":"tv"},token=OWNER)
        self.assertEqual(status,201)
        screen=json.loads(body)
        status,body,_=self.fetch("/api/remote/pair",method="POST",
                                 body={"code":screen["pairing_code"]})
        self.assertEqual(status,201)
        phone=json.loads(body)
        status,body,_=self.fetch("/api/remote/send",method="POST",
                    token=phone["remote_token"],body={"action":"mute"})
        self.assertEqual(status,202)
        pending=json.loads(body)
        self.assertEqual(pending["state"],"pending")
        status,body,_=self.fetch("/api/display/poll",token=screen["display_token"])
        self.assertEqual(status,200)
        delivered=json.loads(body)["commands"]
        self.assertEqual(len(delivered),1)
        self.assertEqual(delivered[0]["action"],"mute")
        status,body,_=self.fetch("/api/display/ack",method="POST",
              token=screen["display_token"],body={
                "command_id":pending["command_id"],"accepted":True})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)["state"],"display_received")
        status,body,_=self.fetch("/api/remote/status?command_id="+
              pending["command_id"],token=phone["remote_token"])
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)["state"],"display_received")
        self.assertNotIn("media_player",json.loads(body))
        status,_,_=self.fetch("/api/display/poll",token=phone["remote_token"])
        self.assertEqual(status,403)

    def test_request_size_and_browser_origin_checks(self):
        status,_,_=self.fetch("/api/profiles",method="POST",body={"label":"x"},
             token=OWNER,headers={"Origin":"http://evil.example"})
        self.assertEqual(status,403)
        status,_,_=self.fetch("/api/profiles",method="POST",body={"label":"x"},
             token=OWNER,headers={"Origin":"http://localhost:"+str(self.port)})
        self.assertEqual(status,404)  # Missing country, region and city
        status,_,_=self.fetch("/api/profiles",method="POST",
             body={"huge":"a"*17000},token=OWNER)
        self.assertEqual(status,413)
        status,_,_=self.fetch("/../../etc/passwd")
        self.assertEqual(status,404)


class ReliableCommandDeliveryTests(unittest.TestCase):
    """Simulated lost HTTP responses and browser reconnects; no real TV calls."""

    def setUp(self):
        self.clock = FakeClock()
        self.broker = LanRemoteBroker(clock=self.clock)
        self.display = self.broker.register(owner="alice", medium="tv")
        self.phone = self.broker.pair(self.display["pairing_code"], peer="phone")
        self.phone_token = self.phone["remote_token"]
        self.screen_token = self.display["display_token"]

    def test_lost_send_response_reuses_command_id(self):
        original = self.broker.send(
            self.phone_token, action="volume_up",
            request_id="phone-command-000001")
        duplicate = self.broker.send(
            self.phone_token, action="volume_up",
            request_id="phone-command-000001")
        self.assertEqual(original["command_id"],duplicate["command_id"])
        self.assertEqual(duplicate["state"],"pending")
        [first] = self.broker.poll(self.screen_token)
        self.assertEqual(first["command_id"],original["command_id"])
        self.assertEqual(self.broker.poll(self.screen_token),[])
        # After ACK, retry the same POST still returns the original command.
        ack = self.broker.acknowledge(
            self.screen_token,first["command_id"],accepted=True)
        self.assertEqual(ack["state"],"display_received")
        again = self.broker.send(
            self.phone_token, action="volume_up",
            request_id="phone-command-000001")
        self.assertEqual(again["command_id"],original["command_id"])
        self.assertEqual(again["state"],"display_received")
        with self.assertRaises(ValueError):
            self.broker.send(self.phone_token,action="mute",
                request_id="phone-command-000001")

    def test_reconnected_visible_display_replays_same_id_not_new_action(self):
        sent=self.broker.send(self.phone_token,action="mute",
                              request_id="phone-command-000002")
        [first]=self.broker.poll(self.screen_token)
        self.clock.forward(4)
        self.assertEqual(self.broker.poll(self.screen_token),[])
        self.clock.forward(1)
        [again]=self.broker.poll(self.screen_token)
        self.assertEqual(first["command_id"],again["command_id"])
        self.assertEqual(first["action"],again["action"])
        self.broker.acknowledge(self.screen_token,again["command_id"],accepted=True)
        repeated_ack=self.broker.acknowledge(
            self.screen_token,again["command_id"],accepted=True)
        self.assertEqual(repeated_ack["state"],"display_received")
        with self.assertRaises(ValueError):
            self.broker.acknowledge(
                self.screen_token,again["command_id"],accepted=False)
        self.clock.forward(10)
        self.assertEqual(self.broker.poll(self.screen_token),[])
        self.assertEqual(self.broker.status(
            self.phone_token,sent["command_id"])["state"],"display_received")

    def test_unacknowledged_delivery_becomes_uncertain_not_success(self):
        sent=self.broker.send(self.phone_token,action="volume_up")
        self.assertEqual(len(self.broker.poll(self.screen_token)),1)
        self.clock.forward(5)
        self.assertEqual(len(self.broker.poll(self.screen_token)),1)
        self.clock.forward(5)
        self.assertEqual(len(self.broker.poll(self.screen_token)),1)
        self.clock.forward(5)
        self.assertEqual(self.broker.poll(self.screen_token),[])
        self.assertEqual(self.broker.status(
            self.phone_token,sent["command_id"])["state"],"delivery_uncertain")
        # A late display ACK may still establish receipt without claiming
        # that the real tuner, renderer or media executor changed state.
        ack=self.broker.acknowledge(
            self.screen_token,sent["command_id"],accepted=True)
        self.assertEqual(ack["state"],"display_received")

    def test_inflight_backpressure_counts_delivered_unacked(self):
        for _ in range(64):
            self.broker.send(self.phone_token,action="volume_up")
        self.assertEqual(len(self.broker.poll(self.screen_token)),32)
        with self.assertRaisesRegex(ValueError,"queue full"):
            self.broker.send(self.phone_token,action="mute")
        # Completing one in-flight command frees one bounded slot.
        pending=[v for v in self.broker._commands.values()
                 if v["state"]=="delivered_unacknowledged"]
        self.broker.acknowledge(
            self.screen_token,pending[0]["command_id"],accepted=True)
        self.assertEqual(self.broker.send(
            self.phone_token,action="mute")["state"],"pending")

    def test_request_id_validation_and_explicit_phone_signout(self):
        for identifier in ("a","bad request id","!unsafe",123):
            with self.assertRaises(ValueError):
                self.broker.send(self.phone_token,action="mute",
                                 request_id=identifier)
        self.broker.disconnect_remote(self.phone_token)
        with self.assertRaises(PermissionError):
            self.broker.send(self.phone_token,action="mute")
        with self.assertRaises(PermissionError):
            self.broker.disconnect_remote(self.phone_token)
        # Remote logout does not terminate the display/other authorized owner.
        self.assertEqual(self.broker.display(self.screen_token).medium,"tv")


class GatewayRetryApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.gateway=RegionalLanGateway(
            Path(self.tmp.name)/"profiles.sqlite",owner_secret=OWNER)
        self.headers={"Host":"localhost:8443"}
        self.owner_headers={**self.headers,
                           "Authorization":"Bearer "+OWNER}

    def tearDown(self):
        self.tmp.cleanup()

    def request(self,method,path,data=None,token=None):
        headers={**self.headers}
        if token:headers["Authorization"]="Bearer "+token
        return self.gateway.dispatch(method,path,headers,data,peer="127.0.0.1")

    def test_repeated_network_post_and_phone_signout(self):
        _,registered=self.request("POST","/api/display/register",
                                   {"medium":"radio"},OWNER)
        _,paired=self.request("POST","/api/remote/pair",
                              {"code":registered["pairing_code"]})
        phone=paired["remote_token"]
        body={"action":"mute","request_id":"retry-test-id-20261105"}
        status,first=self.request("POST","/api/remote/send",body,phone)
        self.assertEqual(status,202)
        status,second=self.request("POST","/api/remote/send",body,phone)
        self.assertEqual(status,202)
        self.assertEqual(first["command_id"],second["command_id"])
        _,display=self.request("GET","/api/display/poll",token=registered["display_token"])
        self.assertEqual(len(display["commands"]),1)
        _,ack=self.request("POST","/api/display/ack",{
            "command_id":first["command_id"],"accepted":True
        },registered["display_token"])
        _,repeat_ack=self.request("POST","/api/display/ack",{
            "command_id":first["command_id"],"accepted":True
        },registered["display_token"])
        self.assertEqual(ack["state"],repeat_ack["state"])
        status,out=self.request("POST","/api/remote/disconnect",{},phone)
        self.assertEqual(status,200)
        self.assertEqual(out["state"],"remote_disconnected")
        with self.assertRaises(GatewayError) as exc:
            self.request("POST","/api/remote/send",body,phone)
        self.assertEqual(exc.exception.status,403)


if __name__ == "__main__":
    unittest.main()
