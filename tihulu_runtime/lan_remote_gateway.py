# SPDX-License-Identifier: AGPL-3.0-only
"""Opt-in HTTPS regional lineup API and cross-device *browser-command* relay.

Experimental single-owner gateway for local development. NO tuner, media
player, subtitles, AI, or recording process is started by this server.
Non-loopback bindings REQUIRE user-supplied HTTPS certificate + key.
Do not put the owner secret in URLs, client source files or a public repo.
"""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import ssl
from threading import RLock
from urllib.parse import parse_qs, urlsplit

from .lan_remote_broker import LanRemoteBroker
from .region_channel_manager import ChannelLineupStore, RegionChannelCatalog

DATA = Path(__file__).resolve().parents[1] / "data"
FRONTEND = Path(__file__).resolve().parents[1] / "prototype"
MAX_BODY = 16_384
MAX_PATH = 1_024


class GatewayError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(message)


class RegionalLanGateway:
    """Finite set of owner/paired/display API operations, no RF control."""

    def __init__(self, db_path: str | Path, *, owner_secret: str,
                 allowed_hosts: tuple[str, ...] = ("localhost","127.0.0.1"),
                 broker: LanRemoteBroker | None = None):
        if (not isinstance(owner_secret, str) or len(owner_secret) < 32
                or not owner_secret.isascii()):
            raise ValueError("Owner bearer secret must be >=32 ASCII characters")
        self.owner_secret = owner_secret
        self.owner_id = "local-owner"
        self.allowed_hosts = frozenset(x.lower() for x in allowed_hosts)
        if not self.allowed_hosts or any(
                not x or "/" in x or "@" in x or ":" in x for x in self.allowed_hosts):
            raise ValueError("Allowed hostnames must be explicitly listed")
        self.catalog = RegionChannelCatalog(DATA/"region_profiles.json",
                          DATA/"region_channel_catalog.json",
                          DATA/"channel_frequency_presets.json")
        self.db_path = str(db_path)
        self.broker = broker or LanRemoteBroker()
        self._db_lock = RLock()
        store = self._store()
        store.close()

    def _store(self) -> ChannelLineupStore:
        return ChannelLineupStore(self.db_path, self.catalog)

    def _authorization(self, headers: dict, *, scope: str) -> tuple[str,str]:
        bearer = headers.get("authorization", "")
        if not bearer.startswith("Bearer ") or len(bearer) > 160:
            raise GatewayError(401,"A bearer session is required")
        token = bearer[7:]
        if not token:
            raise GatewayError(401,"A bearer session is required")
        if scope == "owner":
            if not hmac.compare_digest(token,self.owner_secret):
                raise GatewayError(403,"Owner authorization failed")
            return self.owner_id, token
        if scope == "remote":
            try:
                session = self.broker.remote(token)
                return session.owner,token
            except PermissionError as exc:
                raise GatewayError(403,"Remote pairing required") from exc
        if scope == "display":
            try:
                session = self.broker.display(token)
                return session.owner,token
            except PermissionError as exc:
                raise GatewayError(403,"Display session invalid or expired") from exc
        raise GatewayError(500,"Unknown authorization scope")

    def _owner_or_remote(self, headers: dict) -> tuple[str,str]:
        bearer = headers.get("authorization", "")
        if bearer.startswith("Bearer ") and hmac.compare_digest(
                bearer[7:],self.owner_secret):
            return self.owner_id, "owner"
        owner,_ = self._authorization(headers,scope="remote")
        return owner,"remote"

    def _read(self, owner: str, action):
        with self._db_lock:
            store = self._store()
            try:
                return action(store,owner)
            finally:
                store.close()

    def dispatch(self, method: str, raw_path: str, headers: dict,
                 data: dict | None = None, *, peer: str = "local",
                 secure: bool = False) -> tuple[int, dict]:
        """Return status/JSON; only trusted server handler may call dispatch."""
        if len(raw_path) > MAX_PATH:
            raise GatewayError(414,"Path too long")
        headers = {k.lower():v for k,v in headers.items()}
        raw_host = headers.get("host","")
        hostname = raw_host.split(":")[0].lower()
        if hostname not in self.allowed_hosts:
            raise GatewayError(403,"Unrecognized gateway hostname")
        origin = headers.get("origin")
        expected = ("https://" if secure else "http://") + raw_host
        if origin is not None and origin != expected:
            raise GatewayError(403,"Cross-origin access refused")
        if method not in ("GET","POST"):
            raise GatewayError(405,"Method unavailable")
        parts = urlsplit(raw_path)
        path = parts.path
        params = parse_qs(parts.query)
        def q(name):
            return params.get(name,[""])[0]
        if method == "GET" and path == "/api/health":
            return 200, {"status":"experimental","receiver_integrated":False,
                          "media_player_integrated":False,"ai_integrated":False}
        if method == "POST" and not isinstance(data,dict):
            raise GatewayError(400,"JSON object required")
        d = data or {}
        try:
            if method == "GET" and path == "/api/regions":
                self._authorization(headers,scope="owner")
                return 200, {"countries":[{"iso":iso,"regions":list(regions)}
                           for iso,regions in self.catalog.regions.items()]}
            if method == "GET" and path == "/api/cities":
                self._authorization(headers,scope="owner")
                return 200, {"cities":self.catalog.cities(q("country"),q("region"))}
            if method == "GET" and path == "/api/candidates":
                self._authorization(headers,scope="owner")
                entries = self.catalog.candidates(q("country"),q("region"),q("city"))
                return 200, {"status":"published_not_received","candidates":[{
                    "id":e.id,"name":e.name,"mode":e.kind,
                    "frequency_hz":e.frequency_hz,"source":e.source,
                    "locality":e.locality} for e in entries]}
            if method == "GET" and path == "/api/profiles":
                owner,_ = self._owner_or_remote(headers)
                return 200, {"profiles":self._read(owner,lambda store,o:
                                            store.profiles(owner_id=o))}
            if method == "GET" and path == "/api/items":
                owner,role = self._owner_or_remote(headers)
                medium = q("medium") or "all"
                if role == "remote":
                    session = self.broker.remote(headers["authorization"][7:])
                    if medium not in ("all",session.medium):
                        raise GatewayError(403,"Remote is paired to different medium")
                    medium = session.medium
                return 200, {"items":self._read(owner,lambda store,o:store.items(
                    owner_id=o,profile_id=q("profile_id"),media=medium))}
            if method == "POST" and path == "/api/profiles":
                owner,_ = self._authorization(headers,scope="owner")
                profile = self._read(owner,lambda store,o:store.create(
                    owner_id=o,country=d["country"],region=d["region"],
                    city=d["city"],label=d["label"]))
                return 201, {"profile_id":profile}
            if method == "POST" and path == "/api/items/presets":
                owner,_ = self._authorization(headers,scope="owner")
                ids = self._read(owner,lambda store,o:store.add_presets(
                    owner_id=o,profile_id=d["profile_id"],
                    preset_ids=d["preset_ids"]))
                return 201, {"added_item_ids":ids}
            if method == "POST" and path == "/api/items/custom":
                owner,_ = self._authorization(headers,scope="owner")
                new_id = self._read(owner,lambda store,o:store.add_custom(
                    owner_id=o,profile_id=d["profile_id"],label=d["label"],
                    mode=d["mode"],frequency_hz=d["frequency_hz"]))
                return 201, {"item_id":new_id}
            if method == "POST" and path == "/api/items/edit":
                owner,_ = self._authorization(headers,scope="owner")
                self._read(owner,lambda store,o:store.edit(
                    owner_id=o,profile_id=d["profile_id"],item_id=d["item_id"],
                    label=d["label"],mode=d["mode"],
                    frequency_hz=d["frequency_hz"],offset_hz=d.get("offset_hz",0)))
                return 200, {"state":"manual_unverified"}
            if method == "POST" and path == "/api/items/reorder":
                owner,_ = self._authorization(headers,scope="owner")
                self._read(owner,lambda store,o:store.reorder(
                    owner_id=o,profile_id=d["profile_id"],item_ids=d["item_ids"]))
                return 200, {"state":"saved"}
            if method == "POST" and path == "/api/items/remove":
                owner,_ = self._authorization(headers,scope="owner")
                self._read(owner,lambda store,o:store.remove(
                    owner_id=o,profile_id=d["profile_id"],item_ids=d["item_ids"]))
                return 200, {"state":"removed"}
            if method == "POST" and path == "/api/display/register":
                owner,_ = self._authorization(headers,scope="owner")
                return 201,self.broker.register(owner=owner,medium=d["medium"])
            if method == "POST" and path == "/api/display/revoke":
                owner,_ = self._authorization(headers,scope="owner")
                self.broker.revoke(owner=owner,target_id=d["target_id"])
                return 200,{"state":"revoked"}
            if method == "POST" and path == "/api/remote/pair":
                return 201,self.broker.pair(d["code"],peer=peer)
            if method == "GET" and path == "/api/display/poll":
                _,token = self._authorization(headers,scope="display")
                return 200,{"commands":self.broker.poll(token)}
            if method == "POST" and path == "/api/display/ack":
                _,token = self._authorization(headers,scope="display")
                if type(d.get("accepted")) is not bool:
                    raise ValueError("Boolean accepted field required")
                return 200,self.broker.acknowledge(token,d["command_id"],
                                                    accepted=d["accepted"])
            if method == "POST" and path == "/api/remote/send":
                owner,token = self._authorization(headers,scope="remote")
                session = self.broker.remote(token)
                action = d["action"]
                profile_id = d.get("profile_id","")
                item_id = d.get("item_id","")
                if action in ("select_channel","next_channel","previous_channel"):
                    rows=self._read(owner,lambda store,o:store.items(
                        owner_id=o,profile_id=profile_id,media=session.medium))
                    if not rows:
                        raise ValueError("No saved channels for paired medium")
                    if action == "select_channel" and item_id not in {
                            r["item_id"] for r in rows}:
                        raise GatewayError(403,"Channel not in owner profile")
                return 202,self.broker.send(token,action=action,
                        profile_id=profile_id,item_id=item_id)
            if method == "GET" and path == "/api/remote/status":
                _,token=self._authorization(headers,scope="remote")
                return 200,self.broker.status(token,q("command_id"))
        except GatewayError:
            raise
        except KeyError as exc:
            raise GatewayError(404,"Resource or required field not found") from exc
        except PermissionError as exc:
            raise GatewayError(403,"Operation not authorized") from exc
        except (TypeError,ValueError,OverflowError) as exc:
            raise GatewayError(422,"Invalid request or incompatible saved data") from exc
        raise GatewayError(404,"Endpoint not found")


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "TihuluPrototype/0.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Never log tokens, pairing codes, raw paths or request bodies.
        pass

    def _reply(self,status:int,payload:bytes,mime:str):
        self.send_response(status)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(payload)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header("Connection","close")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self,status:int,value:dict):
        self._reply(status,json.dumps(value,ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8")

    def _run(self,method:str):
        path=urlsplit(self.path).path
        try:
            host=self.headers.get("Host","").split(":")[0].lower()
            if host not in self.server.gateway.allowed_hosts:
                raise GatewayError(403,"Unrecognized gateway hostname")
            if method=="GET" and path in ("/","/app.js"):
                if path=="/":
                    f=FRONTEND/"lan_remote.html";mime="text/html; charset=utf-8"
                else:
                    f=FRONTEND/"lan_remote.js";mime="text/javascript; charset=utf-8"
                self._reply(200,f.read_bytes(),mime)
                return
            if not path.startswith("/api/"):
                raise GatewayError(404,"Endpoint not found")
            data = None
            if method=="POST":
                if self.headers.get("Content-Type","").split(";")[0].strip()!="application/json":
                    raise GatewayError(415,"application/json content required")
                try:
                    length=int(self.headers.get("Content-Length","-1"))
                except ValueError:
                    raise GatewayError(400,"Invalid body length")
                if length < 0 or length > MAX_BODY:
                    raise GatewayError(413,"Body exceeds permitted size")
                try:
                    data=json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError,json.JSONDecodeError):
                    raise GatewayError(400,"Invalid JSON")
            status,result=self.server.gateway.dispatch(method,self.path,
                dict(self.headers),data,peer=self.client_address[0],
                secure=isinstance(self.connection,ssl.SSLSocket))
            self._json(status,result)
        except GatewayError as exc:
            self._json(exc.status,{"error":exc.message})
        except OSError:
            self._json(500,{"error":"Local gateway file unavailable"})
        except Exception:
            self._json(500,{"error":"Internal prototype gateway error"})

    def do_GET(self):
        self._run("GET")

    def do_POST(self):
        self._run("POST")


def build_server(host: str, port: int, gateway: RegionalLanGateway,
                 *, cert: str | None = None, key: str | None = None) -> ThreadingHTTPServer:
    if not (0 <= port <= 65535) or (port == 0 and host not in ("127.0.0.1","localhost","::1")):
        raise ValueError("Invalid listening port")
    if (host not in ("127.0.0.1","localhost","::1") and not (cert and key)):
        raise ValueError("Non-loopback LAN exposure requires TLS certificate and key")
    if bool(cert) != bool(key):
        raise ValueError("Certificate and key must both be present")
    server=ThreadingHTTPServer((host,port),GatewayHandler)
    server.daemon_threads=True
    server.gateway=gateway
    if cert:
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version=ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(certfile=cert,keyfile=key)
        server.socket=ctx.wrap_socket(server.socket,server_side=True)
    return server


def main(argv=None):
    parser=argparse.ArgumentParser(description="Experimental local TV/radio remote relay")
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8443)
    parser.add_argument("--db",required=True,help="Persistent owner lineup SQLite file")
    parser.add_argument("--cert",help="Trusted HTTPS certificate PEM for LAN access")
    parser.add_argument("--key",help="Private PEM key, do not commit")
    parser.add_argument("--hostname",action="append",default=[],
                        help="Allowlisted DNS name (repeat for tihulu.lan/local)")
    args=parser.parse_args(argv)
    secret=os.environ.get("TIHULU_OWNER_TOKEN","")
    if len(secret)<32:
        parser.error("Set TIHULU_OWNER_TOKEN to a strong random secret (>=32 chars)")
    permitted=tuple(dict.fromkeys(("127.0.0.1","localhost",*args.hostname)))
    gateway=RegionalLanGateway(args.db,owner_secret=secret,allowed_hosts=permitted)
    server=build_server(args.host,args.port,gateway,cert=args.cert,key=args.key)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
