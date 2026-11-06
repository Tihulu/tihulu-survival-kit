# Ağ ve Erişim — Tihulu Kit, tihulu.lan, tihulu.local ve Ethernet

> **Durum:** Hedeflenen tasarımın kullanıcı rehberi; henüz Tihulu Core/portal yayımlanmadı. Adresler yalnızca ilgili servisler düzgün kurulmuşsa çalışır. Bu kılavuz hiçbir kişisel Wi-Fi parolası veya gerçek IP bilgisini içermez.

## İlk bakışta önemli bilgiler

| Konu | Bilinmesi gereken |
|---|---|
| Raspberry Pi'nin kendi Wi-Fi SSID'si | **`Tihulu Kit`** (planlanan varsayılan) |
| Wi-Fi hotspot şifresi | **Her cihazda kullanıcıya özgü** ilk kurulum/önceden kişiselleştirme; **GitHub'a yazılmaz** |
| Tihulu yönetici parolası | Hotspot şifresinden **ayrı** ve güçlü |
| Hotspot adresi | `tihulu.lan` |
| Hotspot yedek IP | `10.10.10.10` |
| Ev modem/router erişimi | `tihulu.local` **mDNS uygunsa**, aksi halde router'ın Pi'ye verdiği gerçek LAN IP |
| Ev modeminde `tihulu.lan` | **Ancak router DNS'i yerel alias/host kaydıyla sağlarsa** |
| Ethernet doğrudan bilgisayara | Gerçek Pi Ethernet IP veya desteklenen mDNS; `10.10.10.10` PC Ethernet yedek adresi değildir |
| Dışarıdan internet erişimi | **Varsayılan olarak kapalı/yok**; aynı LAN erişimi ile karıştırmayın |

## Dört bağlantı yöntemi

### A — Pi'nin dahili hotspot'u

- Pi dahili Wi-Fi → SSID **Tihulu Kit**; telefon/tablet/PC bu ağa katılır.
- Planlanan Pi Hotspot DHCP/DNS, `tihulu.lan`'ı `10.10.10.10`'a çözümler.
- Pi internet bağlantısı olmasa da yüklenmiş çevrimdışı Home, Guide, Kiwix/Wikipedia, Kolibri, harita, dosya uygulamaları çalışabilir.
- Tihulu Hotspot **ayrı**; ikinci Wi-Fi istemcisi veya Ethernet interneti için kapatılması gerekmiyor.
- Hotspot sahibi, SSID/şifreyi **Ayarlar → Ağ → Tihulu Hotspot** üzerinden değiştirebilmeyi hedefliyor. Değiştirince telefon yeniden bağlanmak zorunda kalabilir.

### B — Pi Ethernet → ev router/modem

- Pi'nin Ethernet portunu modem/router'ın LAN portuna bağlayın.
- Telefon/PC modem/router'ın kendi Wi-Fi'sindeyse Pi'ye **aynı yerel ağ üzerinden** ulaşabilmeli.
- Modem Pi'ye DHCP ile örnek `192.168.x.y` gibi **gerçek** IP verir; tam adres modeme göre değişir.
- Pi'de Avahi/mDNS, istemcide mDNS ve ağ multicast desteği varsa `tihulu.local` çalışabilir.
- `tihulu.lan` için modeminizin yerel DNS'ine kayıt gerekebilir, kendi başına garanti değildir.
- Modem WAN bağlantısızsa yerel Tihulu uygulamaları yine çalışabilir.

### C — Pi'nin ikinci USB Wi-Fi adaptörü → ev router/modem

- Dahili Pi Wi-Fi **Tihulu Kit** hotspot'u olarak kalır; **ayrı USB Wi-Fi adaptörü** modem/router Wi-Fi'sine istemci olarak bağlanır.
- Modeme bağlı diğer telefon/PC, B seçeneğindeki gibi **aynı Tihulu Home ve uygulamalarına** erişir; Tihulu Kit'e katılması gerekmez.
- İkinci USB adaptörü yoksa bu yöntem mümkün değil; Ethernet ve hotspot seçenekleri kalır.
- Ağ yöneticisi USB adaptörü, modem adı (SSID), şifre, DHCP IP, ağ geçidi, güvenilen LAN ve internet bağlantısını ayrı göstermeyi hedefliyor.
- Tek Wi-Fi adaptörünün aynı anda AP+istemci çalışacağını **garanti etmeyiz**.

### D — Pi Ethernet → doğrudan bilgisayar (modemsiz)

- Pi Ethernet kablosunu masaüstü/dizüstü PC'nin Ethernet portuna veya USB-Ethernet adaptörüne bağlayın.
- PC ve Pi Ethernet arayüzünde **uyumlu IP adresleri** olmalı:
  1. Bilgisayardaki Internet Sharing/ICS bir DHCP adresi sağlıyorsa Pi DHCP'den öğrenebilir.
  2. DHCP yoksa iki uç destekliyorsa IPv4 link-local/Avahi ile keşif yapılabilir.
  3. Olmazsa iki uçta **çakışmayan, kullanıcıca açıkça seçilmiş** izole sabit IPv4 profili gerekebilir.
- `tihulu.local` mDNS varsa deneyin; değilse Pi'nin **gerçek Ethernet IP adresini** PC tarayıcısına yazın. Pi'nin hotspot IP'si `10.10.10.10`, PC Ethernet için otomatik doğru değildir.
- Pi, modem olmadığında bilgisayarın mevcut internetini **otomatik olarak kullanamaz**. Bilgisayarın paylaşımı ayrıca kullanıcı tarafından etkinleştirilmelidir.
- **Router Ethernet'e rogue DHCP/DNS başlatmayın**; yeni link modunun doğru seçildiği doğrulanmalı.

## Bilgisayarın internetini Pi ile paylaşmak (isteğe bağlı)

**Önkoşul:** Bilgisayarın Wi-Fi/başka bir adaptör üzerinden gerçekten interneti var, PC Ethernet portuyla Pi'ye bağlı ve kullanıcı paylaşımı bilerek etkinleştiriyor.

| Bilgisayar OS | PC tarafında planlanan yöntem |
|---|---|
| Windows 10/11 | **Internet Connection Sharing (ICS)**: internet bağlantısını Pi'nin bağlı olduğu Ethernet arayüzüyle paylaşma; Windows'un kendi DHCP/NAT davranışını kullanma |
| macOS | **System Settings → General → Sharing → Internet Sharing**, kaynak internet arayüzünden Ethernet'e paylaşım |
| Linux (NetworkManager kullanan dağıtımlar / Pop!_OS / Ubuntu) | Ethernet IPv4 yöntemini **Shared to other computers** olarak ayarlama; NM DHCP/NAT sağlıyorsa Pi DHCP istemcisi olur |

Bu ayarlar PC işletim sisteminde yapılır; Tihulu web sayfası bir tıkla PC'nin güvenlik duvarını, ağ paylaşımını ya da internetini izinsiz değiştiremez. İşletim sistemi/arayüz/sürüm farklarını ve gerçek DHCP/subnet bilgilerini kontrol edin. PC kapanır, uykuya geçer ya da interneti kesilirse Pi tekrar **internet yok** durumuna dönebilir; yerel Tihulu Kit hotspot'u çalışmaya devam edebilir.

İlk bağlantı için bilgisayarın çevrimdışı olması sorun değildir: doğru doğrudan Ethernet IP'si varsa tarayıcıdaki Tihulu uygulamaları yerel sunucuya ulaşabilir.

Kaynaklar:
- [Apple — Share Internet connection on Mac](https://support.apple.com/guide/mac-help/share-internet-connection-mac-network-users-mchlp1540/mac)
- [NetworkManager `ipv4.method shared`](https://networkmanager.dev/docs/api/latest/settings-ipv4.html)
- [Windows ağ bağlantısı/yönetimi](https://support.microsoft.com/windows)

## Hangi adresi kullanacağım? (ayrıntı)

### `tihulu.lan` — Pi hotspot adlandırması

Bu ad yalnızca Pi'nin **kendi DNS'ine bağlanan** istemciler için kontrolümüzdedir. Ev router'ında da aynı adı istiyorsanız router'da yerel DNS host kaydı/rezervasyon veya bu adın yönlendirilmesini sağlayan bir özellik olmalıdır. Pi'nin bir ağa bağlanması router'daki DNS'i otomatik değiştirmez.

### `tihulu.local` — mDNS

Pi hostname'i `tihulu` ve Avahi/mDNS servisi kullanıldığında aynı yerel ağ bağlantısındaki istemciler `tihulu.local` ile keşfedebilir. Ancak **router konuk Wi-Fi izolasyonu, multicast engelleme, VLAN, istemci mDNS desteği** bunu bozabilir. Çözüm: o arayüzün gerçek Pi IPv4/IPv6 adresini görüntülemek.

### IP adresleri

- Hotspot **`10.10.10.10`**: planlanan sabit AP IP.
- Router üzerinde Pi Ethernet ya da ikinci USB Wi-Fi IP'si: **DHCP tarafından atanır**, örnek adres garantisi yoktur.
- Doğrudan PC Ethernet IP'si: PC paylaşımına, link-local veya bilinçli sabit profil seçimine bağlıdır.
- Tüm aktif Pi IP'leri ve erişim adresleri, cihazın kendi **Ayarlar → Ağ** panelinden veya PC/Pi yerel ağ araçlarından görülebilir. Guide “kopyala” seçeneği sunacak.

## Tarayıcıda güvenli kullanım ve HTTPS

- Temel Tihulu Home ve offline içeriklerin erişimi, doğru LAN IP'si ve HTTP/HTTPS yapılandırmasına bağlıdır.
- **Kamera, mikrofon, GPS/Geolocation ve canlı OCR** için tarayıcıların güvenilir **HTTPS secure context** koşulları kritik önemdedir. Kendi ürettiğiniz sertifikanın iPhone/Android tarafından otomatik güvenildiğini varsaymayın.
- `tihulu.lan`, `tihulu.local`, hotspot IP, router LAN IP ve doğrudan-PC IP farklı **origin/sertifika doğrulama** durumlarına sahip olabilir; kurulum Guide'ı test edilmiş güven kurulum yolunu gösterecek. Bu yol yapılmadan mobil canlı OCR “çalışıyor” şeklinde iddia edilmez.
- Çevrimiçi/Cloud model veya internetten Pi yönetimi **varsayılan kapalı**. Router üzerinde port açma/UPnP açma otomatik yapılmaz.
- Aynı ev modeminde olmak bile yönetici kimlik doğrulamasını kaldırmaz.

Web/platform referansları:
- [Raspberry Pi — .local ve Avahi](https://www.raspberrypi.com/documentation/computers/remote-access.html)
- [RFC 6762 — Multicast DNS](https://www.rfc-editor.org/rfc/rfc6762)
- [MDN — Secure camera / microphone](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- [MDN — Geolocation](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation_API)

## Sorun giderme

| Problem | Önce kontrol |
|---|---|
| `Tihulu Kit` görünmüyor | Core gerçekten yüklü mü? Pi 5 NVMe boot ve AP servisi hazır mı? Güç/soğutma? |
| `tihulu.lan` ev Wi-Fi'sinde çalışmıyor | Router DNS adı bilmiyor olabilir; `tihulu.local` veya Pi router IP'sini dene |
| `tihulu.local` çözülmüyor | Pi mDNS/Avahi, cihaz mDNS desteği, VLAN/konuk Wi-Fi/istemci izolasyonu; gerçek IP'yi kullan |
| 10.10.10.10 ev router'dan açılmıyor | Bu **hotspot** IP'sidir; router'ın Pi'ye verdiği IP'yi kullan |
| Doğrudan PC'de sayfa açılmıyor | Kablo bağlantısı, iki Ethernet IP, PC firewall, DHCP/IPv4LL veya sabit izole profil |
| PC internetine erişilemiyor | PC ICS/Internet Sharing etkin mi? PC'nin interneti gerçek mi? Pi gateway/DNS doğru mu? |
| Web portal açılıyor ama canlı kamera yok | **HTTPS trust**, kullanıcı kamera izni, tarayıcı desteği, uygulamanın OCR paketi |
| Kendi hotspot'um kayboldu | İkinci USB Wi-Fi ile dahili AP karışmış mı? Ağ yönetiminden AP kurtarma; Core imajı/Guide gerekli |

## Ağ erişiminden sonra ne yapacağım?

- [Önce Bunları Bilin](START_HERE.md) — SSID, şifre, adresler
- [Kurulum](INSTALLATION.md) — Tihulu Core/Builder ve Next/Next
- [Canlı OCR ve cihaz izinleri](LIVE_OCR_AND_PERMISSIONS.md)
- [README](../../README.tr.md)

## SSH ile komut satırı erişimi (plan)

Kurulumda güvenli biçimde oluşturulduysa planlanan Linux/SSH hesabı **`tihulu-kit`** olacaktır. SSH şifresi kişisel cihazda ayrı olarak belirlenir; hotspot veya web yönetici şifresi değildir. SSH hizmeti etkinleştirilmeden bağlantı çalışmaz.

```sh
ssh tihulu-kit@tihulu.lan        # Pi'nin kendi hotspot'u; DNS çalışıyorsa
ssh tihulu-kit@10.10.10.10       # Yalnızca Pi hotspot yedek IP
ssh tihulu-kit@tihulu.local      # Ev LAN; mDNS/Avahi çalışıyorsa
```

Router/doğrudan PC Ethernet için `ssh tihulu-kit@<pi-gercek-ip>` komutunda gerçek Pi IP'sini yaz. Ortak şifre GitHub'a kaydedilmez. SSH'yi açma, şifre/anahtar değiştirme, sunucu anahtarı doğrulama ve sorun giderme için [SSH ve Terminal Rehberi](SSH_ACCESS.md). Telefonla günlük kullanım SSH gerektirmez.
