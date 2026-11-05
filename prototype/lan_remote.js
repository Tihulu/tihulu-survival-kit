/* SPDX-License-Identifier: AGPL-3.0-only
 * Experimental LAN controller UI. Receives simulated display commands only.
 * Bearer credentials live in this tab's memory, never the URL or localStorage.
 */
"use strict";
const $ = id => document.getElementById(id);
const node = (tag, text="") => {
  const n=document.createElement(tag);
  n.textContent=text;
  return n;
};
const button = (label,fn) => {
  const el=node("button",label);el.type="button";el.className="alt";el.onclick=fn;return el;
};
const option = (label,value) => {
  const el=node("option",label);el.value=value;return el;
};
function setOptions(el,list){el.replaceChildren(...list.map(p=>option(p.label,p.value)))}
const log = message => { $("status").textContent=message };
let ownerToken="",displayToken="",targetId="",remoteToken="",remoteMedium="tv";
let countries=[],profiles=[],ownerItems=[],phoneItems=[],activeTab="owner",pollTimer=null;
const seenDisplayCommands=new Set();

async function api(path,{method="GET",body=null,token=""}={}){
  const headers={};
  if(token)headers.Authorization="Bearer "+token;
  if(method!=="GET")headers["Content-Type"]="application/json";
  const response=await fetch(path,{method,headers,body:body===null?undefined:JSON.stringify(body),
     credentials:"omit",cache:"no-store",redirect:"error"});
  let value;
  try{value=await response.json()}catch{throw Error("Sunucu geçerli JSON vermedi")}
  if(!response.ok)throw Error(value.error||("HTTP "+response.status));
  return value;
}
function safely(fn){Promise.resolve().then(fn).catch(e=>log("Hata: "+e.message))}
function own(url,opts={}){return api(url,{...opts,token:ownerToken})}
function chosenCity(){return $("custom-city").value.trim()||$("city").value}
function selectedProfile(){return $("owner-profile").value}
function phoneProfile(){return $("phone-profile").value}
function freq(item){return (item.frequency_hz/1e6).toLocaleString("tr-TR",{maximumFractionDigits:3})+" MHz"}
function locationQuery(){return "?country="+encodeURIComponent($("country").value)+
    "&region="+encodeURIComponent($("region").value)+
    "&city="+encodeURIComponent(chosenCity())}
function selectTab(name){
  activeTab=name;
  for(const panel of document.querySelectorAll(".panel"))panel.hidden=panel.id!==name;
  for(const tab of document.querySelectorAll("[data-show]"))tab.className=tab.dataset.show===name?"":"alt";
  if(pollTimer!==null){clearTimeout(pollTimer);pollTimer=null}
  if(name==="display"&&displayToken&&!document.hidden)pollDisplay();
}
for(const tab of document.querySelectorAll("[data-show]"))
  tab.onclick=()=>selectTab(tab.dataset.show);

async function connectOwner(){
  const candidate=$("owner-secret").value;
  if(candidate.length<32)throw Error("En az 32 karakterli owner token gerekli");
  ownerToken=candidate;$("owner-secret").value="";
  const data=await own("/api/regions");
  countries=data.countries;
  setOptions($("country"),countries.map(c=>({label:c.iso==="DE"?"Almanya":"Türkiye",value:c.iso})));
  $("country").value="DE";
  await countryChanged();await loadProfiles();
  log("Yönetici doğrulandı. Kanal listeleri sunucunun SQLite veritabanına kaydedilir.");
}
async function countryChanged(){
  const country=$("country").value;
  const entry=countries.find(c=>c.iso===country);
  setOptions($("region"),(entry?.regions||[]).map(r=>({label:r,value:r})));
  $("region").value=country==="DE"?"Nordrhein-Westfalen":"İzmir";
  await regionChanged();
}
async function regionChanged(){
  const data=await own("/api/cities?country="+encodeURIComponent($("country").value)+
                          "&region="+encodeURIComponent($("region").value));
  const cities=data.cities.length?data.cities:[$("region").value];
  setOptions($("city"),cities.map(city=>({label:city,value:city})));
  if($("country").value==="DE"&&cities.includes("Köln"))$("city").value="Köln";
  if($("country").value==="TR"&&cities.includes("İzmir Merkez"))$("city").value="İzmir Merkez";
  $("custom-city").value="";await loadCandidates();
}
async function loadCandidates(){
  if(!ownerToken)return;
  const data=await own("/api/candidates"+locationQuery());
  const area=$("candidates");area.replaceChildren();
  if(!data.candidates.length)area.append(node("p","Bu şehir için kaynaklı frekans adayı yok. İstersen özel kanal ekle."));
  for(const preset of data.candidates){
    const row=node("div");row.className="item";
    const label=node("label"),input=node("input");input.type="checkbox";input.dataset.preset=preset.id;
    const description=node("span",preset.name+" · "+freq(preset)+" · "+preset.mode);
    const sub=node("small",preset.mode.startsWith("dvb_")?"Satın alınan DVB alıcısı (uyumluluk test edilmedi)":"Ayrı FM/DAB/SDR alıcısı gerekiyor");
    description.append(sub);label.append(input,description);row.append(label);area.append(row);
  }
}
async function createProfile(){
  const label=$("profile-label").value.trim();
  if(!label||!chosenCity())throw Error("Şehir ve liste adı gerekli");
  const response=await own("/api/profiles",{method:"POST",body:{
    country:$("country").value,region:$("region").value,
    city:chosenCity(),label}});
  await loadProfiles(response.profile_id);
  log("Bölge listesi sunucuya kaydedildi; yayın taraması yapılmadı.");
}
async function loadProfiles(keep=""){
  if(!ownerToken)return;
  const response=await own("/api/profiles");
  profiles=response.profiles;
  const old=keep||selectedProfile();
  setOptions($("owner-profile"),profiles.map(p=>({label:p.label+" · "+p.city,value:p.profile_id})));
  if(profiles.some(p=>p.profile_id===old))$("owner-profile").value=old;
  await loadOwnerItems();
}
async function loadOwnerItems(){
  if(!selectedProfile()){$("owner-items").replaceChildren(node("p","Henüz liste yok."));return}
  const response=await own("/api/items?profile_id="+encodeURIComponent(selectedProfile()));
  ownerItems=response.items;renderOwnerItems();
}
async function addSelected(){
  if(!selectedProfile())throw Error("Önce liste oluştur");
  const preset_ids=[...document.querySelectorAll("[data-preset]:checked")]
    .map(x=>x.dataset.preset);
  if(!preset_ids.length)throw Error("En az bir kutucuk seç");
  const result=await own("/api/items/presets",{method:"POST",
    body:{profile_id:selectedProfile(),preset_ids}});
  await loadOwnerItems();
  log(result.added_item_ids.length+" kanal adayı sunucuya eklendi. Otomatik tuning yok.");
}
async function addCustom(){
  if(!selectedProfile())throw Error("Önce bir bölge listesi oluştur");
  const hz=Math.round(Number($("custom-frequency").value)*1e6);
  await own("/api/items/custom",{method:"POST",body:{profile_id:selectedProfile(),
    label:$("custom-label").value,mode:$("custom-mode").value,frequency_hz:hz}});
  await loadOwnerItems();log("Özel kanal kaydedildi (yayın henüz alınmadı).");
}
async function moveItem(index,direction){
  const position=index+direction;
  if(position<0||position>=ownerItems.length)return;
  const ids=ownerItems.map(p=>p.item_id);
  [ids[index],ids[position]]=[ids[position],ids[index]];
  await own("/api/items/reorder",{method:"POST",
     body:{profile_id:selectedProfile(),item_ids:ids}});
  await loadOwnerItems();
}
async function removeItem(item){
  await own("/api/items/remove",{method:"POST",
    body:{profile_id:selectedProfile(),item_ids:[item.item_id]}});
  await loadOwnerItems();
}
async function editItem(item,box){
  const name=box.querySelector("[data-field=name]").value;
  const mode=box.querySelector("[data-field=mode]").value;
  const frequency_hz=Math.round(Number(box.querySelector("[data-field=frequency]").value)*1e6);
  const offset_hz=Math.round(Number(box.querySelector("[data-field=offset]").value)*1000);
  if(!Number.isSafeInteger(frequency_hz)||!Number.isSafeInteger(offset_hz))
    throw Error("Geçerli frekans ve ince ayar gerekli");
  await own("/api/items/edit",{method:"POST",body:{
    profile_id:selectedProfile(),item_id:item.item_id,label:name,mode,
    frequency_hz,offset_hz}});
  await loadOwnerItems();log("Kanal değişti; alıcı kendiliğinden ayarlanmadı.");
}
function renderOwnerItems(){
  const area=$("owner-items");area.replaceChildren();
  for(let i=0;i<ownerItems.length;i++){
    const item=ownerItems[i],row=node("div");row.className="item";
    row.append(node("strong",(i+1)+". "+item.label));
    row.append(node("small",item.mode+" · "+freq(item)+" · "+item.state));
    const actions=node("div");actions.className="controls spaced";
    actions.append(button("↑",()=>safely(()=>moveItem(i,-1))),
      button("↓",()=>safely(()=>moveItem(i,1))),
      button("Sil",()=>safely(()=>removeItem(item))));
    const editor=node("div");editor.className="controls spaced";editor.hidden=true;
    function inp(name,value,type="text"){
      const holder=node("label",name);holder.className="field";
      const input=node("input");input.dataset.field=name.toLowerCase();
      input.type=type;input.value=value;holder.append(input);editor.append(holder);return input;
    }
    inp("Name",item.label);
    const modeLabel=node("label","Mode");modeLabel.className="field";
    const sel=node("select");sel.dataset.field="mode";
    setOptions(sel,["dvb_t2","dvb_t","dvb_c","fm","dab","am","nfm","usb","lsb"]
         .map(m=>({label:m,value:m})));sel.value=item.mode;
    modeLabel.append(sel);editor.append(modeLabel);
    const freqField=inp("Frequency",item.frequency_hz/1e6,"number");freqField.step=".001";
    const offsetField=inp("Offset",item.offset_hz/1000,"number");offsetField.min="-500";offsetField.max="500";
    editor.append(button("Kaydet",()=>safely(()=>editItem(item,editor))));
    actions.append(button("Düzenle",()=>{editor.hidden=!editor.hidden}));
    row.append(actions,editor);area.append(row);
  }
}
async function registerDisplay(){
  if(!ownerToken)throw Error("Önce kurulum sekmesinde yönetici token'ıyla bağlan");
  const x=await own("/api/display/register",{method:"POST",
    body:{medium:$("display-medium").value}});
  displayToken=x.display_token;targetId=x.target_id;
  seenDisplayCommands.clear();
  $("display-title").textContent=x.medium.toUpperCase()+" · Tarayıcı ekranı kayıtlı";
  $("display-code").textContent="Telefon eşleştirme kodu: "+x.pairing_code+" (120 saniye)";
  $("display-detail").textContent="Yalnızca tarayıcı komutları bekleniyor; canlı yayın oynatıcısı yok.";
  log("Ekran oturumu açıldı. Kodu yalnızca eşleştirmek istediğin telefona gir.");
  if(activeTab==="display")pollDisplay();
}
async function revokeDisplay(){
  if(!targetId)return;
  await own("/api/display/revoke",{method:"POST",body:{target_id:targetId}});
  targetId="";displayToken="";
  seenDisplayCommands.clear();
  if(pollTimer!==null){clearTimeout(pollTimer);pollTimer=null}
  $("display-title").textContent="Ekran bağlantısı kapatıldı";$("display-code").textContent="";
  log("Ekran ve eşleştirilmiş telefon oturumları geçersiz.");
}
async function pollDisplay(){
  if(activeTab!=="display"||!displayToken||document.hidden)return;
  const token=displayToken;
  try{
    const result=await api("/api/display/poll",{token});
    // If the tab was hidden or the owner revoked/replaced the display during
    // the request, do not act on the stale response. Broker may retry later.
    if(activeTab!=="display"||document.hidden||token!==displayToken)return;
    for(const cmd of result.commands){
      // Retried delivery has the SAME command_id. Never show/apply twice.
      if(!seenDisplayCommands.has(cmd.command_id)){
        seenDisplayCommands.add(cmd.command_id);
        if(seenDisplayCommands.size>256){
          seenDisplayCommands.delete(seenDisplayCommands.values().next().value);
        }
        $("display-title").textContent="Alınan demo komutu: "+cmd.action;
        $("display-detail").textContent="Kanal profil kodu: "+(cmd.profile_id||"yok")+
          " · Fiziksel TV veya yayın oynatımı değiştirilmedi.";
      }
      // A lost ACK response may be repeated; server accepts same result.
      await api("/api/display/ack",{method:"POST",token,
        body:{command_id:cmd.command_id,accepted:true}});
    }
  }catch(e){log("Display bağlantısı: "+e.message)}
  finally{
    if(activeTab==="display"&&displayToken===token&&!document.hidden)
      pollTimer=setTimeout(pollDisplay,2500);
  }
}
async function pairPhone(){
  const result=await api("/api/remote/pair",{method:"POST",body:{code:$("pair-code").value}});
  remoteToken=result.remote_token;remoteMedium=result.medium;
  $("pair-code").value="";
  $("phone-status").textContent="Eşleşti: "+remoteMedium.toUpperCase()+
    " (yalnızca komut iletimi, canlı oynatma yok)";
  await loadPhoneProfiles();
}
async function loadPhoneProfiles(){
  const result=await api("/api/profiles",{token:remoteToken});
  setOptions($("phone-profile"),result.profiles.map(p=>({
    label:p.label+" · "+p.city,value:p.profile_id})));
  await loadPhoneItems();
}
async function loadPhoneItems(){
  if(!remoteToken||!phoneProfile()){phoneItems=[];$("phone-channel").replaceChildren();return}
  const result=await api("/api/items?profile_id="+encodeURIComponent(phoneProfile()),
                      {token:remoteToken});
  phoneItems=result.items;
  setOptions($("phone-channel"),phoneItems.map(x=>({
    label:x.label+" · "+freq(x),value:x.item_id})));
}
async function remoteSend(action){
  if(!remoteToken)throw Error("Önce telefonunu 8 haneli kodla eşleştir");
  let profile_id="",item_id="";
  if(["select_channel","next_channel","previous_channel"].includes(action)){
    profile_id=phoneProfile();
    if(action==="select_channel")item_id=$("phone-channel").value;
    if(!profile_id||(action==="select_channel"&&!item_id))throw Error("Kanal listesi/kanal seç");
  }
  if(!globalThis.crypto||typeof crypto.randomUUID!=="function"){
    throw Error("Güvenli rastgele istek kimliği için HTTPS/localhost gerekiyor");
  }
  const payload={action,profile_id,item_id,request_id:crypto.randomUUID()};
  let result;
  try{
    result=await api("/api/remote/send",{method:"POST",token:remoteToken,body:payload});
  }catch(e){
    // Only retry a transport failure, not a rejected API request. The same
    // request ID makes a network retry safe against duplicate volume actions.
    if(!(e instanceof TypeError))throw e;
    result=await api("/api/remote/send",{method:"POST",token:remoteToken,body:payload});
  }
  $("phone-status").textContent="Komut sırada: "+action+" — gerçek tuner ayarlanmadı.";
  setTimeout(async()=>{
    if(!remoteToken)return;
    try{
      const current=await api("/api/remote/status?command_id="+encodeURIComponent(result.command_id),
          {token:remoteToken});
      $("phone-status").textContent=action+" · "+current.state+
        " — tarayıcı ACK, medya oynatımı değildir.";
    }catch(e){$("phone-status").textContent=e.message}
  },3500);
}

$("connect-owner").onclick=()=>safely(connectOwner);
$("country").onchange=()=>safely(countryChanged);
$("region").onchange=()=>safely(regionChanged);
$("city").onchange=()=>safely(loadCandidates);
$("custom-city").oninput=()=>safely(loadCandidates);
$("new-profile").onclick=()=>safely(createProfile);
$("owner-profile").onchange=()=>safely(loadOwnerItems);
$("select-visible").onclick=()=>document.querySelectorAll("[data-preset]").forEach(x=>x.checked=true);
$("add-presets").onclick=()=>safely(addSelected);
$("add-custom").onclick=()=>safely(addCustom);
$("register-display").onclick=()=>safely(registerDisplay);
$("revoke-display").onclick=()=>safely(revokeDisplay);
async function disconnectPhone(){
  const token=remoteToken;
  remoteToken="";
  $("phone-profile").replaceChildren();
  $("phone-channel").replaceChildren();
  $("phone-status").textContent="Telefon eşleşmesi kapatıldı.";
  if(token){
    try{
      await api("/api/remote/disconnect",{method:"POST",token,body:{}});
      log("Telefon sunucudaki oturumundan çıkış yaptı.");
    }catch(e){log("Yerel token temizlendi. Sunucu iptalini doğrula: "+e.message)}
  }
}

$("pair").onclick=()=>safely(pairPhone);
$("disconnect-phone").onclick=()=>safely(disconnectPhone);
$("phone-profile").onchange=()=>safely(loadPhoneItems);
$("phone-select").onclick=()=>safely(()=>remoteSend("select_channel"));
for(const b of document.querySelectorAll("[data-action]"))
  b.onclick=()=>safely(()=>remoteSend(b.dataset.action));
document.addEventListener("visibilitychange",()=>{
  if(document.hidden&&pollTimer!==null){clearTimeout(pollTimer);pollTimer=null}
  if(!document.hidden&&activeTab==="display"&&displayToken&&pollTimer===null)pollDisplay();
});
