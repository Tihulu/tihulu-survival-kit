/* Tihulu Flight Radar: real observations only, responsive single-page PWA view.
 * No sample planes, guessed position, remote receivers, auto polling while OFF,
 * unapproved online maps or automatic geolocation prompts.
 */
"use strict";
(() => {
const $ = id => document.getElementById(id);
const canvas = $("sky"), ctx = canvas.getContext("2d");
const GERMANY={lat:51.1657,lon:10.4515,zoom:6};
const state = {
  planes: [], selected: null, camera: {...GERMANY}, receiver: null,
  userMoved: false, follow: false, session: null, csrf: null,
  timer: null, busy: false, lastFocus: null, initialAutoFocus: false
};
const toRad = Math.PI / 180;
function point(a) {
  if (!a || !Number.isFinite(a.latitude) || !Number.isFinite(a.longitude) ||
      Math.abs(a.latitude) > 90 || Math.abs(a.longitude) > 180) return null;
  return {lat:a.latitude,lon:a.longitude};
}
function fresh(a) {
  return a && a.position_available === true &&
    Number.isFinite(a.position_age_seconds) &&
    a.position_age_seconds >= 0 && a.position_age_seconds <= 60 &&
    !!point(a);
}
function km(a,b) {
  const y1=a.lat*toRad,y2=b.lat*toRad,dy=(b.lat-a.lat)*toRad,
        dx=(b.lon-a.lon)*toRad;
  const h=Math.sin(dy/2)**2+Math.cos(y1)*Math.cos(y2)*Math.sin(dx/2)**2;
  return 6371.0088*2*Math.asin(Math.min(1,Math.sqrt(Math.max(0,h))));
}
function chooseFocus(planes, ref) {
  const points=planes.filter(fresh);
  if (!points.length) return null;
  if (ref) {
    let best=points[0],d=km(ref,point(best));
    for(const a of points.slice(1)) {const n=km(ref,point(a));if(n<d){best=a;d=n;}}
    return {aircraft:best,method:"nearest",distance:d};
  }
  // Germany is a *selection heuristic* without a real receiver/GPS position.
  // It is not a claimed user location; never generate an aircraft marker here.
  const sample=points.slice(0,600);
  let best=sample[0],d=km(GERMANY,point(best));
  for(const a of sample.slice(1)){
    const n=km(GERMANY,point(a));if(n<d){best=a;d=n;}
  }
  return {aircraft:best,method:"default-region heuristic",distance:d};
}
function focusNearest(force=false) {
  if(state.userMoved&&!force)return;
  const selected=chooseFocus(state.planes,state.receiver);
  if(!selected){
    const center=state.receiver||GERMANY;
    state.camera={lat:center.lat,lon:center.lon,zoom:state.camera?.zoom||6};
    $("mapHint").textContent=state.receiver?
      "Receiver/device location; no fresh aircraft position.":
      "Germany fallback viewport; no aircraft or receiver location assumed.";
    if(force)state.userMoved=false;
    paint();return;
  }
  state.camera={lat:selected.aircraft.latitude,lon:selected.aircraft.longitude,
                zoom:state.camera?.zoom||7};
  if(force)state.userMoved=false;
  state.lastFocus=selected;
  $("mapHint").textContent=(selected.method==="nearest"?"Nearest reported aircraft":
    "Reported aircraft chosen relative to Germany map default")+
    ": "+(selected.aircraft.callsign||selected.aircraft.icao||"Unknown");
  paint();
}
function clamp(x,a,b){return Math.max(a,Math.min(b,x));}
function wy(lat){let a=clamp(lat,-85,85)*toRad;return (1-Math.log(Math.tan(a)+1/Math.cos(a))/Math.PI)/2;}
function xx(lon,z){return (lon+180)/360*(256*2**z);}
function yy(lat,z){return wy(lat)*256*2**z;}
function pixel(a){
  if(!state.camera)return null;
  const z=state.camera.zoom,w=256*2**z;
  let dx=xx(a.lon,z)-xx(state.camera.lon,z);
  if(dx>w/2)dx-=w;if(dx< -w/2)dx+=w;
  return {x:canvas.clientWidth/2+dx,y:canvas.clientHeight/2+
    yy(a.lat,z)-yy(state.camera.lat,z)};
}
function coordAt(x,y){
  if(!state.camera)return null;
  const z=state.camera.zoom,w=256*2**z,
        X=xx(state.camera.lon,z)+x-canvas.clientWidth/2,
        Y=yy(state.camera.lat,z)+y-canvas.clientHeight/2;
  const n=Math.PI*(1-2*Y/w);
  return {lat:clamp(Math.atan(Math.sinh(n))/toRad,-85,85),
          lon:((X/w*360+180)%360+360)%360-180};
}
function resize(){
  const dpr=Math.min(2,window.devicePixelRatio||1),
        w=Math.max(1,canvas.clientWidth),h=Math.max(1,canvas.clientHeight);
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);paint();
}

/* Optional public OSM raster tiles are requested only after the user selects
 * Online OpenStreetMap and only for the current viewport. No prefetch, offline
 * downloads, background fetch, third-party SDK or persistent service-worker
 * cache. The offline coordinate grid remains available without Internet.
 * Public tile policy/attribution: https://operations.osmfoundation.org/policies/tiles/ */
const osmTiles=new Map();
let osmActive=0;
const TILE_LIMIT=64, MAX_IN_FLIGHT=6;
function drawOptionalOnlineTiles(w,h) {
  if($("mapLayer").value!=="osm" || !state.camera) return;
  const z=Math.floor(state.camera.zoom),world=2**z;
  const originX=xx(state.camera.lon,z)-w/2,originY=yy(state.camera.lat,z)-h/2;
  const minX=Math.floor(originX/256),maxX=Math.floor((originX+w)/256);
  const minY=Math.max(0,Math.floor(originY/256));
  const maxY=Math.min(world-1,Math.floor((originY+h)/256));
  // Bounds are the *visible* tiles, not a surrounding corridor or a cache
  // prefetch. Avoid an extreme monitor/zoom generating an unbounded query.
  let visible=0;
  for(let y=minY;y<=maxY;y++) for(let x=minX;x<=maxX;x++) {
    if(++visible>30) return;
    const normalizedX=((x%world)+world)%world;
    const key=z+"/"+normalizedX+"/"+y;
    const xpos=x*256-originX,ypos=y*256-originY;
    const entry=osmTiles.get(key);
    if(entry?.ready) {
      ctx.drawImage(entry.img,xpos,ypos,256,256);
      continue;
    }
    if(entry || osmActive>=MAX_IN_FLIGHT) continue;
    const image=new Image();
    const tile={img:image,ready:false};
    osmTiles.set(key,tile);osmActive++;
    // Preserve default browser Referer behavior; do not spoof tile origins,
    // cache-bust or bypass the provider's network cache directives.
    image.onload=()=>{
      tile.ready=true;osmActive--;
      if($("mapLayer").value==="osm")paint();
    };
    image.onerror=()=>{
      osmActive--;
      osmTiles.delete(key);
      $("mapHint").textContent="Online map tiles unavailable; coordinate grid remains usable.";
      // Do not re-request failed public tiles automatically.
      osmTiles.set(key,{failed:true});
    };
    image.src="https://tile.openstreetmap.org/"+key+".png";
    while(osmTiles.size>TILE_LIMIT)osmTiles.delete(osmTiles.keys().next().value);
  }
}

function paint(){
  const w=canvas.clientWidth,h=canvas.clientHeight;
  ctx.clearRect(0,0,w,h);ctx.fillStyle="#102435";ctx.fillRect(0,0,w,h);
  if(state.camera)drawOptionalOnlineTiles(w,h);
  ctx.strokeStyle="#355266";ctx.lineWidth=1;ctx.fillStyle="#a5c1d4";
  ctx.font="11px system-ui";
  if(!state.camera) {
    ctx.fillStyle="#d5e1ed";ctx.font="14px system-ui";
    ctx.textAlign="center";ctx.fillText("Waiting for verified aircraft positions",w/2,h/2);
    ctx.fillText("Local receive-only ADS-B",w/2,h/2+23);ctx.textAlign="left";
    return;
  }
  const z=state.camera.zoom,step=z<4?30:z<6?10:z<9?2:z<12?.5:.1;
  // A light local geographic coordinate grid, not fake offline OSM tiles.
  const corners=[coordAt(0,0),coordAt(w,h)];
  if(corners.every(Boolean)) {
    let lo=Math.max(-180,Math.min(corners[0].lon,corners[1].lon)),
        hi=Math.min(180,Math.max(corners[0].lon,corners[1].lon));
    if(hi-lo>300){lo=-180;hi=180;}
    for(let lon=Math.ceil(lo/step)*step;lon<=hi;lon+=step) {
      const p=pixel({lat:state.camera.lat,lon});if(!p)continue;
      ctx.beginPath();ctx.moveTo(p.x,0);ctx.lineTo(p.x,h);ctx.stroke();
      if(p.x>=5&&p.x<=w-45)ctx.fillText(lon.toFixed(step<1?1:0)+"°",p.x+4,16);
    }
    let ymin=Math.max(-85,Math.min(corners[0].lat,corners[1].lat)),
        ymax=Math.min(85,Math.max(corners[0].lat,corners[1].lat));
    for(let lat=Math.ceil(ymin/step)*step;lat<=ymax;lat+=step){
      const p=pixel({lat,lon:state.camera.lon});if(!p)continue;
      ctx.beginPath();ctx.moveTo(0,p.y);ctx.lineTo(w,p.y);ctx.stroke();
      if(p.y>=15&&p.y<=h-5)ctx.fillText(lat.toFixed(step<1?1:0)+"°",6,p.y-3);
    }
  }
  if(state.receiver) {
    const p=pixel(state.receiver);
    if(p){ctx.strokeStyle="#81d7c1";ctx.beginPath();ctx.arc(p.x,p.y,8,0,2*Math.PI);ctx.stroke();
      ctx.beginPath();ctx.moveTo(p.x-10,p.y);ctx.lineTo(p.x+10,p.y);
      ctx.moveTo(p.x,p.y-10);ctx.lineTo(p.x,p.y+10);ctx.stroke();}
  }
  for(const a of state.planes.filter(fresh)) {
    const p=pixel(point(a));if(!p||p.x< -30||p.x>w+30||p.y< -30||p.y>h+30)continue;
    const active=a.key===state.selected;
    ctx.save();ctx.translate(p.x,p.y);
    if(Number.isFinite(a.track_deg))ctx.rotate(a.track_deg*toRad);
    ctx.fillStyle=active?"#ffdf8c":"#9cceeb";ctx.strokeStyle="#142735";ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(0,-12);ctx.lineTo(-5,4);ctx.lineTo(0,2);
    ctx.lineTo(5,4);ctx.closePath();ctx.fill();ctx.stroke();ctx.restore();
    if(active) {
      ctx.fillStyle="#fff0c5";ctx.font="12px system-ui";
      ctx.fillText(a.callsign||a.icao||"Aircraft",p.x+9,p.y-12);
    }
  }
}
function changeZoom(delta){
  if(!state.camera)return;
  state.camera.zoom=clamp(state.camera.zoom+delta,2,15);
  state.userMoved=true;state.follow=false;syncFollow();paint();
}
function syncFollow(){$("follow").setAttribute("aria-pressed",String(state.follow));}
canvas.addEventListener("pointerdown",e=>{if(!state.camera)return;canvas.setPointerCapture(e.pointerId);
  state.drag={x:e.clientX,y:e.clientY,moved:false};});
canvas.addEventListener("pointermove",e=>{if(!state.drag||!state.camera)return;
  const dx=e.clientX-state.drag.x,dy=e.clientY-state.drag.y;
  if(Math.abs(dx)+Math.abs(dy)>1){state.drag.moved=true;state.userMoved=true;state.follow=false;syncFollow();}
  const center=coordAt(canvas.clientWidth/2-dx,canvas.clientHeight/2-dy);
  if(center)state.camera={...state.camera,lat:center.lat,lon:center.lon};
  state.drag.x=e.clientX;state.drag.y=e.clientY;paint();
});
canvas.addEventListener("pointerup",e=>{
  const d=state.drag;state.drag=null;if(!d||d.moved)return;
  const box=canvas.getBoundingClientRect(),x=e.clientX-box.left,y=e.clientY-box.top;
  let selected=null,nearest=18;
  for(const a of state.planes.filter(fresh)){
    const p=pixel(point(a)),dist=p?Math.hypot(p.x-x,p.y-y):Infinity;
    if(dist<nearest){nearest=dist;selected=a;}
  }
  if(selected)selectPlane(selected.key);
});
canvas.addEventListener("wheel",e=>{e.preventDefault();changeZoom(e.deltaY<0?1:-1);},{passive:false});
$("zoomIn").onclick=()=>changeZoom(1);
$("zoomOut").onclick=()=>changeZoom(-1);
$("mapLayer").addEventListener("change",()=>{
  if($("mapLayer").value==="osm") {
    $("notice").textContent="Online map requested. Visible tiles are fetched from OpenStreetMap with attribution. No offline tile download.";
  } else {
    // The grid is always available; no network calls when grid is selected.
    $("notice").textContent="Offline coordinate grid selected. No map tile requests.";
  }
  paint();
});
$("focusNearest").onclick=()=>{focusNearest(true);state.initialAutoFocus=true;};
$("showGermany").onclick=()=>{
 state.camera={...GERMANY};state.userMoved=true;state.follow=false;
 syncFollow();$("mapHint").textContent=
   "Germany map viewport (not a receiver or user location).";paint();
};
$("focusReceiver").onclick=()=>{
 if(!state.receiver){$("mapHint").textContent="Set receiver coordinates or grant location first.";return;}
 state.camera={...state.receiver,zoom:state.camera?.zoom||9};
 state.userMoved=false;paint();
};
$("fitAll").onclick=()=>{
 const p=state.planes.filter(fresh);if(!p.length)return;
 const lat=p.reduce((a,b)=>a+b.latitude,0)/p.length;
 const lon=p.reduce((a,b)=>a+b.longitude,0)/p.length;
 state.camera={lat,lon,zoom:6};state.userMoved=false;paint();
};
$("follow").onclick=()=>{
 state.follow=!state.follow;syncFollow();
 if(state.follow&&state.selected)followSelected();
};
function followSelected(){
 const a=state.planes.find(x=>x.key===state.selected);
 if(a&&fresh(a)){state.camera={lat:a.latitude,lon:a.longitude,
   zoom:state.camera?.zoom||10};state.userMoved=false;paint();}
}
function rememberReceiver(v){
 if(!v||!Number.isFinite(v.lat)||!Number.isFinite(v.lon)||
    Math.abs(v.lat)>90||Math.abs(v.lon)>180)return false;
 state.receiver=v;
 try{localStorage.setItem("tihulu-flight-receiver-location",JSON.stringify(v));}catch(_){}
 return true;
}
try{
 const saved=JSON.parse(localStorage.getItem("tihulu-flight-receiver-location")||"null");
 if(saved)rememberReceiver(saved);
}catch(_){}
if(state.receiver)focusNearest(true);
$("receiverLocation").onclick=()=>{
 const lat=prompt("Receiver latitude (-90 to 90):",state.receiver?.lat??"");
 if(lat===null)return;
 const lon=prompt("Receiver longitude (-180 to 180):",state.receiver?.lon??"");
 if(lon===null)return;
 const v={lat:Number(lat),lon:Number(lon)};
 if(!lat.trim()||!lon.trim()||!rememberReceiver(v)){
   $("notice").textContent="Invalid coordinates. Nothing was changed.";return;
 }
 $("notice").textContent="Receiver position saved in this browser only.";
 if(!state.userMoved)focusNearest(true);
};
$("deviceLocation").onclick=()=>{
 if(!navigator.geolocation){$("notice").textContent="Geolocation unavailable.";return;}
 navigator.geolocation.getCurrentPosition(p=>{
   if(rememberReceiver({lat:p.coords.latitude,lon:p.coords.longitude})){
     $("notice").textContent="Device location saved in this browser.";
     if(!state.userMoved)focusNearest(true);
   }
 },()=>{$("notice").textContent="Location not permitted or unavailable.";},
 {timeout:8000,enableHighAccuracy:false,maximumAge:60000});
};
function detailLabel(name,value){
 const cell=document.createElement("div"),label=document.createElement("strong");
 label.textContent=name;cell.append(label,document.createTextNode(value==null?"Unknown":String(value)));
 return cell;
}
function selectPlane(key){
 state.selected=key;
 const plane=state.planes.find(a=>a.key===key);
 $("fullMapLink").href=(plane&&fresh(plane)&&/^[0-9a-f]{6}$/i.test(plane.icao||""))?
   "/flight-radar/map?icao="+plane.icao+"&noIsolation":
   "/flight-radar/map";
 renderList();renderDetails();
 if(state.follow)followSelected();else paint();
}
function renderDetails(){
 const node=$("details");node.replaceChildren();
 const a=state.planes.find(x=>x.key===state.selected);
 if(!a){const p=document.createElement("p");p.className="muted";
   p.textContent="Select a received aircraft for genuine details.";node.append(p);return;}
 const title=document.createElement("h2");title.textContent=a.callsign||a.icao||"Unidentified aircraft";
 const grid=document.createElement("div");grid.className="detailgrid";
 const fields=[
 ["ICAO",a.icao],["Aircraft type",a.aircraft_type],
 ["Latitude",fresh(a)?a.latitude?.toFixed(5):"Not available"],
 ["Longitude",fresh(a)?a.longitude?.toFixed(5):"Not available"],
 ["Barometric altitude (ft)",a.altitude_ft],
 ["Ground speed (kt)",a.ground_speed_kt],
 ["Track (°)",a.track_deg],["Vertical speed (ft/min)",a.vertical_rate_fpm],
 ["Position source",a.position_kind||"No valid position"],
 ["Position age (s)",a.position_age_seconds],
 ["Source IDs",(a.source_ids||[]).join(", ")||a.source_id],
 ["Local RSSI (dBFS)",a.rssi_dbfs],
 ];
 for(const [name,value] of fields)grid.append(detailLabel(name,value));
 node.append(title,grid);
}
function renderList(){
 const list=$("airlist");list.replaceChildren();
 const search=$("search").value.trim().toLowerCase();
 let items=state.planes.filter(a=>
   !search||(a.callsign||"").toLowerCase().includes(search)||
    (a.icao||"").toLowerCase().includes(search)||
    (a.aircraft_type||"").toLowerCase().includes(search));
 const sort=$("sort").value;
 if(sort==="nearest"&&state.receiver)items.sort((a,b)=>{
   const d=x=>fresh(x)?km(state.receiver,point(x)):Infinity;
   return d(a)-d(b);});
 else if(sort==="altitude")items.sort((a,b)=>(b.altitude_ft??-1e10)-(a.altitude_ft??-1e10));
 else if(sort==="callsign")items.sort((a,b)=>(a.callsign||a.icao||"").localeCompare(b.callsign||b.icao||""));
 if(!items.length){const p=document.createElement("p");p.className="empty";
   p.textContent=search?"No matching received aircraft.":"No fresh aircraft contacts.";
   list.append(p);return;}
 for(const a of items.slice(0,600)){
   const row=document.createElement("button");row.type="button";row.setAttribute("role","option");
   row.setAttribute("aria-selected",String(a.key===state.selected));
   const name=document.createElement("b");name.textContent=a.callsign||a.icao||"Unidentified";
   const meta=document.createElement("small");
   meta.textContent=(fresh(a)?"Position":"Mode S / no valid position")+" · "+
     (a.source_ids||[a.source_id]).join(" + ");
   const age=document.createElement("small");
   age.textContent=Number.isFinite(a.contact_age_seconds)?
       Math.round(a.contact_age_seconds)+"s ago":"Age unknown";
   row.append(name,age,meta);row.onclick=()=>selectPlane(a.key);
   list.append(row);
 }
}
$("search").addEventListener("input",renderList);
$("sort").addEventListener("change",renderList);
function setStatus(text){$("live").textContent=text;$("status").textContent=text;}
async function api(path,options={}) {
 const r=await fetch(path,{credentials:"same-origin",cache:"no-store",...options});
 let payload;
 try{payload=await r.json();}catch(_){throw Error("Invalid backend response.");}
 if(!r.ok)throw Error(payload.error||"Request unavailable");
 return payload;
}
async function start(){
 if(state.session)return;
 if(!state.csrf){$("notice").textContent="Portal authorization/CSRF integration is not installed.";return;}
 $("connect").disabled=true;
 try{
   const mode=$("mode").value,online_allowed=$("online").value==="on";
   const result=await api("/api/flight-radar/session",{
     method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":state.csrf},
     body:JSON.stringify({mode,online_allowed})});
   state.session=result.session_id;
   $("stop").disabled=false;setStatus("Connected");
   $("notice").textContent=result.receiver_attached?
     "Local SDR lease attached. Waiting for actual readsb observations.":
     "Local tuner not attached. Online availability depends on configured providers.";
   await poll();
   state.timer=setInterval(poll,3000);
 }catch(e){$("notice").textContent=e.message;setStatus("Unavailable");}
 finally{$("connect").disabled=!!state.session;}
}
async function stop(){
 if(!state.session)return;
 const sid=state.session;
 clearInterval(state.timer);state.timer=null;
 try{await api("/api/flight-radar/session/"+encodeURIComponent(sid),{
   method:"DELETE",headers:{"X-CSRF-Token":state.csrf}});}
 catch(e){$("notice").textContent="Session release was not confirmed: "+e.message;return;}
 state.session=null;state.planes=[];state.selected=null;
 state.camera=state.receiver?{...state.receiver,zoom:7}:{...GERMANY};
 state.userMoved=false;state.initialAutoFocus=false;
 $("connect").disabled=false;$("stop").disabled=true;setStatus("Stopped");
 $("count").textContent="—";$("positioned").textContent="—";
 $("notice").textContent="No background aircraft polling. Session released.";
 renderList();renderDetails();paint();
}
const PROVIDER_LINKS = Object.freeze({
 "adsb.lol": "https://www.adsb.lol/docs/open-data/api",
 "adsb.fi": "https://adsb.fi",
 "opensky": "https://opensky-network.org/about/terms-of-use"
});
function showProviderAttribution(entries){
 const target=$("providerAttributions");target.replaceChildren();
 if(!Array.isArray(entries)||!entries.length){
   target.textContent="No configured internet source in use; antenna observations are local.";
   return;
 }
 target.append(document.createTextNode("Online sources: "));
 for(const [index, entry] of entries.entries()){
   if(!entry || typeof entry.provider!=="string")continue;
   const verifiedUrl=PROVIDER_LINKS[entry.provider];
   if(!verifiedUrl)continue;
   if(index)target.append(document.createTextNode(" · "));
   const link=document.createElement("a");
   link.href=verifiedUrl;link.target="_blank";link.rel="noopener noreferrer";
   link.textContent=entry.provider+" ("+String(entry.license||"terms apply")+")";
   link.style.color="#9ed5fa";
   target.append(link);
 }
}
async function poll(){
 if(!state.session||state.busy)return;
 state.busy=true;
 try{
   const data=await api("/api/flight-radar/aircraft?session="+encodeURIComponent(state.session));
   if(!Array.isArray(data.aircraft))throw Error("Invalid aircraft feed.");
   state.planes=data.aircraft;
   showProviderAttribution(data.provider_attributions);
   $("count").textContent=String(data.count);
   $("positioned").textContent=String(data.positioned);
   const online=Object.values(data.source_status||{}).filter(x=>x==="live").length;
   $("sourceState").textContent=String(online);
   setStatus(online?"Live":data.data_available?"Active":"Source unavailable");
   if(!data.data_available)$("notice").textContent=
     "No active source is available. Internet disconnection is not an empty sky.";
   if(!state.userMoved&&!state.initialAutoFocus&&state.planes.some(fresh)){
     focusNearest();state.initialAutoFocus=true;
   } else if(state.follow&&state.selected)followSelected();
   else paint();
   renderList();renderDetails();
 }catch(e){setStatus("Degraded");$("notice").textContent=e.message;}
 finally{state.busy=false;}
}
$("connect").onclick=start;$("stop").onclick=stop;
$("mode").onchange=()=>{if(state.session)$("notice").textContent="Close the current session to change source mode.";};
$("online").onchange=()=>{if(state.session)$("notice").textContent="Close the current session to change online access.";};
$("mobileMap").onclick=()=>$("sheet").dataset.sheet="closed";
$("mobileAircraft").onclick=()=>$("sheet").dataset.sheet="half";
$("mobileSettings").onclick=()=>$("sheet").dataset.sheet="open";
window.addEventListener("resize",resize);
if(typeof ResizeObserver!=="undefined")new ResizeObserver(resize).observe(canvas);
resize();
api("/api/flight-radar/bootstrap").then(x=>{
 state.csrf=x.csrf_token;
 $("notice").textContent=new URLSearchParams(location.search)
   .has("full_map_unavailable")?
   "Full tar1090 map assets are not installed. Lightweight offline map is in use.":
   "Choose a source mode. No receiver is started automatically.";
}).catch(()=>{$("notice").textContent=
 "Preview only until an authenticated Survival Kit gateway supplies CSRF and service permissions.";});
})();
