# Tihulu Survival Kit

**Language / Dil:** [English](README.md) · **Türkçe** · Deutsch *(planlanıyor)*

**Türkçe:** Raspberry Pi 5 için tasarlanan taşınabilir, **internet olmadan da kullanılabilen** bilgi, eğitim, harita, afet hazırlığı, yerel yapay zekâ ve radyo platformu.

**English:** A planned portable, offline-first knowledge, learning, mapping, emergency-information, local AI and receive-only radio hub for Raspberry Pi 5 — accessible from phones, tablets and computers through a local browser.

> [!IMPORTANT]
> **ÖNCE OKUYUN — Proje şu anda planlama/geliştirme hazırlığı aşamasında (5 Kasım 2026).** Henüz yayımlanmış, çalışan bir **Tihulu Core imajı, kurulum sihirbazı, web portalı veya doğrulanmış donanım kurulumu yoktur.** Bu README ve rehberler hedeflenen ürünü ve kurulumu açıklar; var olmayan kurulum komutları veya “çalışıyor” iddiaları içermez.
>
> İlk açılış, Wi-Fi SSID, şifre, adresler ve sorun giderme için önce **[Başlangıç: Önce Bunları Bilin](docs/START_HERE_TR.md)** ve ardından **[Kurulum Rehberi](docs/INSTALLATION_TR.md)** sayfalarını okuyun.

## Engineering development status (November 5, 2026)

**Main branch:** Planning documentation, user guides and [development/language guidelines](AGENTS.md). No installable Tihulu Core image, production portal, or validated Raspberry Pi appliance is available yet.

**Experimental code:** [Draft PR #1 — On-Demand Window & Task Manager](https://github.com/Tihulu/tihulu-survival-kit/pull/1) contains a Python service/job policy prototype, an English standalone browser demo, unit tests and a candidate TV/radio text-network directory. Those are **not installed services**; automated unit-test success is not Pi hardware validation. See [Development Status](docs/DEVELOPMENT_STATUS.md) for pending modules, tuner and news-feed requirements.

**Dil:** GitHub geliştirme iletişiminde İngilizce tercih edilir, ancak Türkçe ve Almanca dosyalar serbesttir. Ana sayfa [İngilizce](README.md), bu belge ise Türkçe sürümdür. Almanca sürüm ileride hazırlanacaktır.

## İlk bilinmesi gerekenler / First-boot essentials

| Konu | Planlanan değer / açıklama |
|---|---|
| **Tihulu'nun kendi Wi-Fi adı (SSID)** | **`Tihulu Kit`** |
| **Wi-Fi şifresi** | **Cihaza özgü, kullanıcı tarafından oluşturulur**. Bu GitHub deposunda veya dağıtılan genel imajda *asla gerçek parola yayımlanmaz*. |
| **Yönetici hesabı** | İlk güvenli kayıt sırasında oluşturulur; Wi-Fi şifresinden **farklı** tutulur. |
| **Hotspot web adresi** | **`tihulu.lan`** (Pi kendi AP/DNS hizmeti kurulduğunda) |
| **Hotspot yedek IP adresi** | **`10.10.10.10`** (yalnızca Pi hotspot'u için) |
| **Modeme Ethernet veya ikinci USB Wi-Fi ile bağlı Pi** | **`tihulu.local`** (mDNS destekleniyorsa) veya router'ın Pi'ye verdiği **gerçek LAN IP** |
| **Ev modeminde `tihulu.lan`** | Ancak modem/router'ın kendi DNS'inde alias/host kaydı varsa; **otomatik garanti edilmez** |
| **Bilgisayara doğrudan Ethernet** | Pi'nin gerçek doğrudan Ethernet IP'si veya desteklenen `tihulu.local`; modem gerekmez |
| **Tarayıcı kamera/GPS** | Gerçek kullanıcı izni **ve güvenilir HTTPS** gerekebilir; HTTP ile portal açılması bu özellikleri garanti etmez |

**`Tihulu Kit` ağını görmüyorsanız:** Raspberry Pi OS Lite'ı tek başına kurmak Tihulu hotspot'unu veya `tihulu.lan`'ı oluşturmaz. Önce gerçek Tihulu Core imajı/installer'ın yayımlanmış olması gerekir. Şu anda böyle bir yayımlanmış sürüm yok.

**Network note (EN):** `tihulu.lan` is intended for the Pi-managed hotspot DNS; `tihulu.local` relies on mDNS/Avahi support. On a home router LAN or a direct computer Ethernet link, use the Pi's actual interface IP if name discovery fails. Never assume the hotspot IP is the router-assigned LAN IP.

## Nedir? / What is Tihulu?

Tihulu Survival Kit; Raspberry Pi 5 + NVMe depolama üzerinde, yerel **Home** arayüzünü bir telefondan, tabletten veya bilgisayardan **tarayıcıyla** açmayı hedefler. Kullanıcı, internet bağlantısının olup olmamasına bağlı kalmadan *önceden yüklenmiş* arşivleri ve servisleri kullanabilmeli; internet varsa açık izinle seçili veri paketlerini yenileyebilmelidir.

Proje şu kaynaklardan esinlenen/uyumluluk hedefleyen **modüler** bir yaklaşıma sahiptir:

- [HAS Prepper Disk](https://github.com/schematrix/HAS_Prepper_Disk) ve [Internet-in-a-Box](https://github.com/iiab/iiab): survival kaynakları, çevrimdışı bilgi ve eğitim içeriğini koruma.
- [Kiwix](https://www.kiwix.org/): tek paylaşılan Kiwix, **orijinal tam İngilizce ve Türkçe Wikipedia ZIM** arşivleri ve diğer seçilmiş içerikler.
- [Kolibri](https://learningequality.org/kolibri/): tek paylaşılan Kolibri ve yerel eğitim kursları.
- [Project NOMAD](https://github.com/Crosstalk-Solutions/project-nomad): seçili yararlı araçları Pi ARM64 koşullarına uyarlama; x86-64 container'larını körlemesine kopyalamama.
- [OpenStreetMap](https://www.openstreetmap.org/): gerçek çevrimdışı rota ağı ve geocoder ile harita.
- Yerel GGUF modeller, paylaşılan OCR/ASR/Translator, izinli dosya arama, USB receive-only SDR deneyleri.

Bu sistem bir **kamusal acil uyarı servisi, resmî afet uygulaması ya da profesyonel tıbbi cihaz yerine geçmez**. Kaynakların güncelliği ve gerçek çevrimdışı kapsam açıkça gösterilmelidir.

## Donanım hedefi / Hardware target

| Bileşen | Hedef |
|---|---|
| Bilgisayar | Raspberry Pi 5, **8 GB RAM**, ARM64 |
| Depolama | 1 TB NVMe, Pi 5 uyumlu M.2/PCIe HAT; örnek Acer FA100 |
| Güç/soğutma | Uygun Pi 5 USB-C güç profili, aktif fan, test edilmiş batarya/powerbank (isteğe bağlı) |
| Yerel ağ | Dahili Wi-Fi **Tihulu Kit** hotspot + Ethernet |
| İsteğe bağlı uplink | İkinci USB Wi-Fi adaptörü ile ev router'ına/telefon hotspot'una bağlanma, Ethernet veya PC Internet Sharing |
| Radyo | İsteğe bağlı alıcı-only USB SDR, anten/uygun frekans/mevzuat testleri |
| Erişim | iOS/Android telefon, tablet, Windows/macOS/Linux bilgisayar — web tarayıcısı |

**8 GB RAM sınırı önemlidir:** Kiwix/Kolibri, browser, OCR, yerel AI, haritalar ve radio aynı anda devreye gireceğinde sıra/bellek yönetimi gerekir. Performans verileri gerçek Pi 5 testlerinden önce doğrulanmış sayılmamalıdır.

## Kurulum / Installation

**Bugün:** Bu depo henüz indirilebilir Tihulu imajı veya çalışan kurulum komutu içermiyor. Raspberry Pi OS Lite kurmak yalnızca işletim sistemini kurar; Tihulu Home'u, Guide'ı, hotspot'u veya uygulamaları getirmez. Güvenilir bir Tihulu sürümü yayımlandığında **[Releases](https://github.com/Tihulu/tihulu-survival-kit/releases)** ve gerçek doğrulanmış checksum'ları esas alınacak.

**Yayımlandığında hedeflenen akış:**

1. **Tihulu Minimal Core**, **Full Offline** veya **Custom/Hybrid** imajını seçin; masaüstünde hazırlayanlar için **Complete Setup on PC** seçeneği.
2. Doğrulanmış imajı [Raspberry Pi Imager](https://www.raspberrypi.com/software/) üzerinden **Use Custom** ile doğru NVMe diskine yazın. Yazma işlemi disk verilerini silebilir.
3. NVMe'yi Raspberry Pi 5'e takıp açın. Core gerçekten kuruluysa **Tihulu Kit** Wi-Fi'si üzerinden veya Pi'nin modeme/PC'ye bağlı yerel Ethernet/USB Wi-Fi bağlantısından Tihulu'ya erişin.
4. **Cihaza özgü** güvenli yönetici ve Wi-Fi parolasını kurun. Dil ve ülke/bölgeyi seçin.
5. **Hızlı Kurulum**, **Adım adım (Next/Next)** ya da **Gelişmiş** modundan birini kullanın. Bir özet ekranında mevcut, indirilecek ve sonradan kurulacak uygulama/veri/model paketlerini görün; büyük indirmelere ayrıca izin verin.
6. Güvenli Core tamamlandığında Home/Guide'a geçin; eksik olan gerçek Wikipedia, harita/rota ağı, kurs, Translator/OCR ve AI paketleri **Software & Update Center** üzerinden sonradan kurulabilir.

**Ayrıntılı kurulum:** [docs/INSTALLATION_TR.md](docs/INSTALLATION_TR.md)

## Bağlantı seçenekleri / Access paths

```text
                     TELEFON / TABLET / BİLGİSAYAR
                                 |
              +------------------+-------------------+
              |                  |                   |
         Tihulu Kit AP      EV MODEM/ROUTER     DOĞRUDAN PC KABLO
              |                  |                   |
          Pi dahili         Pi Ethernet veya      Pi Ethernet
          Wi-Fi AP          2. USB Wi-Fi           arayüzü
              |                  |                   |
     tihulu.lan / IP      tihulu.local / IP      Link IP / .local
              \_________________|___________________/
                                 |
                     Tihulu Home / Auth
                                 |
                     Aynı uygulama servisleri
```

Modeme veya ikinci USB Wi-Fi ile bağlanınca aynı ağdaki bilgisayar/telefonların **Tihulu Kit hotspot'una katılması gerekmez**. Pi'yi doğrudan PC Ethernet'e bağlamak da modem olmadan yerel portal erişimini hedefler. Windows ICS/macOS Internet Sharing/Linux NetworkManager ile PC'den Pi'ye internet paylaşımı **ayrı, kullanıcı kontrolündeki bir işlemdir**; kablo otomatik internet vermez.

**[Tam ağ ve adres rehberi](docs/NETWORK_ACCESS_TR.md)**

## Özellik kapsamı / Planned features

| Alan | Planlanan özellikler |
|---|---|
| **Offline bilgi** | HAS/IIAB işlevlerini koruma, tam orijinal EN+TR Wikipedia ZIM, Kiwix, survival/onarım/sağlık vb. koleksiyonlar |
| **Eğitim** | Kolibri kursları, offline videolar/dersler, öğrenim ilerlemesi |
| **Haritalar** | Bölge bazlı OSM; tiles yanında gerçek rota grafiği, geocoder/POI; izinli telefon GPS ile A→B yürüyüş/araç/bisiklet |
| **Emergency** | Resmî kaynaklardan hedeflenen 24 ülke/bölge; yerel/ülke/global önemli filtre; orijinal uyarı ve zaman damgası |
| **Radio** | İsteğe bağlı USB SDR FM/AM/LW/SW uygun kaynak alımı, gerçek orijinal ses kayıtları ve isteğe bağlı canlı altyazı |
| **Local AI** | Light/Balanced/deneysel Maximum model sınıfları; Hugging Face GGUF kurulumu, izinli çoklu kaynak RAG, sohbet geçmişi/projeler |
| **Translator/OCR** | Sayfa/PDF/belge çevirisi; **telefon kamerasıyla canlı OCR**, aralıklı tarama ve açık istekle Translator/AI |
| **Browser** | Offline wiki/kurs/PDF ve normal tarayıcı işleri; Çince/başka dilde önce çevir, sonra kaynaklı AI özet/soru-cevap |
| **Files/Office/Media** | NVMe ve USB, izinli Nextcloud/WebDAV, PDF, Office belgeleri, müzik/video/SRT-VTT altyazı |
| **Sistem araçları** | FlatNotes, CyberChef adayları; Service/Startup/Energy, RAM/swap/Storage Manager; ortak Update Center |
| **Kurulum/Guide** | Hızlı/Next/Advanced, yerel dil/region seçimleri, telefon üzerinden kullanım, şifre/ağ rehberi, imaj oluşturma |

Bunlar **uygulandı** listesi değil, **hedeflenen özelliklerdir**. Daha kapsamlı tablo, bağımlılıklar ve veri güvenliği: **[Özellikler ve Sistem Mimarisi](docs/FEATURES_AND_ARCHITECTURE_TR.md)**.

## Telefon kamerasıyla canlı OCR / Live camera OCR

Yeni planlanan **Canlı OCR** akışı:

**Kamera izni iste → Ön/arka kamera ve metin alanı seç → Canlı görüntüden kontrollü aralıklarla OCR → Düzenle/kopyala → İstersen Çevir/AI'a Sor → Kaydet veya durdur.**

- Telefon/masaüstü kamerasını **Tihulu sunucusu otomatik açamaz**. İzin her istemci cihazda ve tarayıcıda gerekir.
- Kamera akışı ve kareler **varsayılan olarak kalıcı kayıt değildir**. İşlem/aktarılacak kare/dosya/retention açıkça gösterilir; kayıt ayrıca istenir.
- Çince gibi kurulu OCR/Translator paketi yoksa hata dürüstçe gösterilir, uydurma çeviri/özet yapılmaz.
- **Güvenilir HTTPS** gereklidir; yerel HTTP veya tarayıcının güvenmediği bir sertifika kamera/konum API'larını engelleyebilir.
- **Mobil:** `Dosya Seç`, galeriden seçim, fotoğraf çek veya canlı kamera; **masaüstü:** drag-and-drop ve dosya seçici; ayrıca desteklenen izinli webcam.
- OCR, Translator ve LLM **Hard ON ve kuruluysa** kullanıcı eylemiyle açılıp iş bitince RAM'i bırakır; **Hard OFF** için “Yalnızca bu işlem / Kalıcı aç / Açma” uyarısı.

**[Canlı OCR ve tüm cihaz izinleri rehberi](docs/LIVE_OCR_AND_PERMISSIONS_TR.md)**

## Offline, güvenlik ve veri koruma / Security & privacy

- Yerel sistem ve yayınların **çalışması için dış internete sürekli bağlantı zorunlu olmayacak**; eksik paketlerin sonradan indirilmeleri gerekir.
- Yerel Wi-Fi şifresi, yönetici parolası, sertifika anahtarları, cihaz konumu, özel dosyalar ve üçüncü taraf API tokenları **bu açık GitHub deposuna yazılmaz**. Public README kişisel şifre göstermez.
- Kullanıcı **kamera, mikrofon, geolocation, Dosya Seç, NVMe/USB indeksleme, WAN/cellular data, üçüncü taraf AI/API, dosya yükleme ve original audio recording** için ayrı izin/veri kullanımı görür.
- Başka bilgisayarın veya telefonun tüm diskini tarayıcıdan sessizce tarama mümkün/izinli değildir; yalnızca seçilen/sürüklenen dosyalar işlenir.
- Ev LAN erişimi **internet üzerinden kamusal erişim** değildir. Yönetici girişi her linkte gerekir, otomatik port-forward/UPnP yok.
- Emergency Master kapatılırsa yeni uyarı alınmayabilir; var olan orijinal resmî metin/kayıtları koruma ve STALE ibaresi gerekir.
- İlk kurulumda **unique credentials, trustable HTTPS ve installer checksums** uygulanmadan güvenli dağıtım ilan edilmeyecek.

## Durum, yol haritası ve testler / Project status

**Current public implementation status:** planning and documentation. **No deployable Tihulu image, installer, Home/Guide app, live OCR, LLM, radio stack or passing Raspberry Pi integration tests have been published.**

Geliştirme hedefleri: önce boot/NVMe/core/first-owner/AP/HTTPS, sonra ortak uygulama/servis kataloğu ve basit web arayüzü, gerçek offline HAS/Kiwix/Kolibri, bölgesel maps/routing, resmi kaynak Emergency, sonra yerel LLM/RAG, OCR/Translator/ASR, dosyalar/Office/media/radio ve full uçtan uca test. Her modül yayımlandığında uygulandı/test edildi/deneysel/planlandı olarak işaretlenmeli.

Test koşulları: **Pi 5 8GB RAM/ısı/batarya**, Ethernet modem ve doğrudan PC, ikinci USB Wi-Fi, Android/iPhone Safari/Chrome ve PC tarayıcıları, HTTPS secure origin ve yerel DNS/mDNS, gerçek ZIM/rota paketi, kamera canlı OCR hız/izin/dil, güvenli model bellek tahsisi, SDR gerçek alım/ses kaydı ve kullanıcı verisinin korunması.

## Rehberler / Documentation

| Belge | İçerik |
|---|---|
| **[Önce Bunları Bilin](docs/START_HERE_TR.md)** | İlk açılış; `Tihulu Kit`, şifre, `tihulu.lan`, `tihulu.local`, acil sorun giderme |
| **[Kurulum Rehberi](docs/INSTALLATION_TR.md)** | Donanım, NVMe imaj, Raspberry Pi Imager, Hızlı/Standart/Gelişmiş, internet/eksik paketler |
| **[Ağ ve Erişim](docs/NETWORK_ACCESS_TR.md)** | Hotspot, Ethernet modem, ikinci USB Wi-Fi, doğrudan PC, ICS, mDNS, SSL, IP |
| **[Canlı Kamera OCR ve İzinler](docs/LIVE_OCR_AND_PERMISSIONS_TR.md)** | Kamera canlı OCR, dosya seçme, drag-drop, saklama/izin, Translator/AI, HTTPS |
| **[Özellikler ve Mimari](docs/FEATURES_AND_ARCHITECTURE_TR.md)** | Tüm planlanan modüller, teknik kısıtlar, kaynaklar, güvenlik ve geliştirme testi |

## Katkı ve kaynak hakları / Contributions & licensing

Proje açık kaynaklı ekosistemlerden yararlanmayı hedefler; ancak bu depoda **şu anda yayımlanmış bir Tihulu uygulama lisansı veya lisanslanmış uygulama kodu bulunduğunu varsaymayın**. Her üçüncü taraf bileşenin kendi lisansı, kaynak/attribution ve redistribüsyon koşulları ayrıca doğrulanmalıdır. Kaynak isimleri burada teknik bağlam ve atıf içindir, bütün projelerin bu depoya kopyalandığı anlamına gelmez.

Katkı yapmak isteyenler, önce bu README'deki “planned vs implemented” ayrımını ve rehberleri okuyup [Issues](https://github.com/Tihulu/tihulu-survival-kit/issues) üzerinden uygulanabilir öneri/hata raporu paylaşabilir; **gerçek Wi-Fi şifresi, erişim tokeni, özel konum ve kişisel dosyalar paylaşılmamalıdır**.

---

**Status summary / İngilizce:** Tihulu Survival Kit is **not yet released**. Target defaults: SSID **`Tihulu Kit`** (unique password, never published); AP URL **`tihulu.lan`** / **`10.10.10.10`**, home LAN **`tihulu.local`** when mDNS works or the Pi's actual IP. Planned interfaces include Ethernet to router **or directly to a computer**, second USB Wi-Fi to router, optional host internet sharing, and user-authorized phone **live camera OCR**. All are **design goals requiring implementation and tests**. See the linked installation and security guides.
