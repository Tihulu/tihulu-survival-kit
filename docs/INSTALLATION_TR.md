# Tihulu Survival Kit — Kurulum ve İlk Yapılandırma Rehberi

> **5 Kasım 2026, proje aşaması:** Bu belge yayımlanması **planlanan** kurulumun eksiksiz kullanıcı rehberi taslağıdır. Bu depoda henüz çalışan Tihulu Core imajı, Image Builder, GitHub kurucu betiği veya dağıtım/release **bulunmuyor**. Aşağıdaki “Tihulu'yu kurun” adımları **ilgili dosyalar yayımlandıktan sonra** uygulanabilir; Raspberry Pi OS Lite kurmak, kendiliğinden Tihulu uygulamalarını kurmaz. Belirtilmeyen bir `curl | bash` komutunu çalıştırmayın.

## İçindekiler

1. [Donanım ve gereksinimler](#1-donanım-ve-gereksinimler)
2. [Kurulum yöntemini seçin](#2-kurulum-yöntemini-seçin)
3. [NVMe'ye imaj yazın](#3-nvmeye-imaj-yazın)
4. [İlk açılış / Tihulu Kit ve adresler](#4-ilk-açılış--tihulu-kit-ve-adresler)
5. [Hızlı / Adım adım / Gelişmiş sihirbaz](#5-hızlı--adım-adım--gelişmiş-sihirbaz)
6. [İçerik, model ve harita indirme](#6-içerik-model-ve-harita-indirme)
7. [Ağ ve bilgisayardan internet paylaşımı](#7-ağ-ve-bilgisayardan-internet-paylaşımı)
8. [HTTPS, telefon kamerası ve canlı OCR](#8-https-telefon-kamerası-ve-canlı-ocr)
9. [Servisler ve güncelleme](#9-servisler-ve-güncelleme)
10. [Doğrulama, sorun giderme, veri güvenliği](#10-doğrulama-sorun-giderme-veri-güvenliği)

## Donanım yükseltme ve AI yapılandırması (Aşama 5 geliştirme)

**Hâlen plan/deneysel backend:** Kullanıcının talebi doğrultusunda CPU-only, AI HAT+ 2 (Hailo-10H) ve güvenli özel LAN üzerinden uzak AI sunucusu tasarlanmaktadır. Donanım sonradan eklendiğinde Tihulu işletim sistemini yeniden kurmak zorunda olmamak hedeflenir. Gerçek kuruluma bağlanan web sihirbazı henüz yayımlanmadı.

Geliştirici denetimi (mevcut repo/uygun Python ortamı gerekir):

    python3 -m tihulu_runtime.ai_setup --probe-npu --pcie-nvme-boot

Bu komut yalnızca donanım ve sürücü durumunu inceleyen bir JSON önerisi üretir; model indirmez, AI HAT sürücüsü kurmaz, disk taşımaz ve Tihulu Core'u yüklemez. Pi 5'in PCIe bağlantısında mevcut NVMe HAT ile AI HAT+ 2 için donanım topolojisini kesinlikle doğrulayın. Eski boot diskini biçimlendirmeyin. Modele ait harici SSD çıkarılırsa model kullanılmaz olarak işaretlenmeli, otomatik yeniden indirme yapılmamalıdır. Uzak sunucu için kimlik doğrulamalı güvenilir HTTPS gerekir; internete açık ham Ollama API'si kullanılmamalıdır.

Ayrıntılı durum ve güvenli yükseltme: [Aşama 5 Donanım Uyumluluğu](ai/HARDWARE_AWARE_STAGE5.md) ve [Uzak AI Server Kurulum Rehberi](ai/REMOTE_AI_SERVER_SETUP.md).

## 1. Donanım ve gereksinimler

**Hedef sistem, test edilmesi gereken başlangıç profili:**

- Raspberry Pi 5 **8 GB**, aktif soğutma, Pi 5 NVMe HAT/M.2 adaptörü ve uygun güç kaynağı (Pi 5 için gereken USB-C güç profili ve cihaz tüketimini kontrol edin).
- **1 TB NVMe** (planda Acer FA100), uygun yazma için PC'de USB–NVMe adaptörü; imaj yazma hedef diskindeki **tüm verilerin silinebileceğini** unutmayın.
- İlk başlatma için akıllı telefon, tablet veya bilgisayar (iOS/Android/Windows/macOS/Linux).
- İsteğe bağlı: ikinci **USB Wi-Fi adaptörü** (modem Wi-Fi'sine istemci olarak bağlanmak için); Ethernet kablosu (modeme veya doğrudan PC'ye), USB SDR anten/alıcı, powerbank, USB disk.
- İnternet **zorunlu değildir** ancak boş Core imajında tam Wikipedia, kurşun geçirmez harita/rota verileri değil, kurulu olmayan Kiwix ZIM'leri, modeller ve dil paketleri daha sonra indirilmek zorundadır.

Bu cihaz profili **hedef tasarımdır**, henüz resmî Tihulu sistem testi tamamlanmamıştır. Kasa/soğutucu, radyo ve batarya seçimleri ayrıca doğrulanacaktır.

## 2. Kurulum yöntemini seçin

| Gelecekteki yöntem | Kullanım | Avantaj / dikkat |
|---|---|---|
| **Tihulu Minimal Core** | Telefonda ilk kurulum ve ihtiyaç halinde içerik indirme | Küçük imaj; Pi ilk açılışta kendi Wi-Fi ağını/Guide'ı sunar. Büyük paketler eksik olabilir |
| **Tihulu Full Offline** | Başlangıçta içeriklerle offline çalışmak | Çok büyük imaj; gerçekten paketlenmiş içerik listesini kontrol edin |
| **Tihulu Custom/Hybrid Image Builder** | PC'den gerekli içerikleri seçmek | Her bileşen **imaja dahil / sonra kur / isteğe bağlı çıkar** |
| **Complete Setup on PC** | Pi'ye takmadan tüm seçimleri doğrulanmış imaja kurmak | Tamamlanmışsa Pi'de sihirbazı tekrarlamayabilir |
| **Raspberry Pi OS Lite + GitHub (gelişmiş)** | Sistem geliştirme / elle kurulum | **Henüz çalışan Tihulu bootstrap/installer yok.** Raspberry Pi OS Lite tek başına hotspot, `tihulu.lan`, Home veya Guide sunmaz |

**Şu anda indirilebilir bir Tihulu sürümü yok.** Yayınlandığında yalnızca [Releases](https://github.com/Tihulu/tihulu-survival-kit/releases) bölümünde gerçekten listelenen sürümleri ve duyurulan SHA-256 imza/hash'lerini kullanın. Boş veya bulunmayan Releases sayfası bir arıza değildir; proje erken aşamadadır.

### Sistem geliştiricileri için geçici OS hazırlığı (Tihulu kurulumu DEĞİL)

Tihulu imajı yayımlanmadan Pi'yi denemek isteyenler [resmî Raspberry Pi Imager](https://www.raspberrypi.com/software/) ile Raspberry Pi OS Lite 64-bit ARM64 imajını desteklenen NVMe/medyaya yazabilir. Bu **yalnızca Raspberry Pi OS kurulumudur**; Tihulu Wi-Fi hotspot/portal/uygulama servisleri **çalışmaz**. Geliştirme sırasında şifreleri yönetici tarafından belirleyin; gizli bilgileri GitHub issue'larına veya halka açık günlük dosyalarına koymayın.

## 3. NVMe'ye imaj yazın

*Bu adımlar bir Tihulu imajı yayımlandıktan sonra geçerlidir.*

1. PC'de doğru, doğrulanmış `.img`/`.img.xz` dosyasını edinin; kaynağı, sürümü ve SHA-256 checksum'ını **gerçekte mevcut** sürüm bilgisiyle kontrol edin.
2. NVMe'yi PC'ye USB–NVMe adaptörüyle bağlayın. **Diskteki bilgiler silinebilir**; hedefi model/kapasite/seriyle iki kere doğrulayın.
3. **Raspberry Pi Imager → Use Custom / Özel imaj kullan** üzerinden Tihulu imajını seçin, doğru NVMe aygıtına yazın ve doğrulamayı bekleyin. Stock Imager'ın Tihulu model/Wikipedia/harita seçimleri yapacağı iddia edilmez; bunlar ayrı Tihulu Image Builder tasarımının işidir.
4. NVMe'yi Pi 5 HAT'e takın, soğutmayı bağlayın, doğru güç sağlayın; ilk boot'un tamamlanmasını bekleyin. HAT, firmware/EEPROM ve NVMe boot uyumluluğu cihaz üzerinde doğrulanmalıdır.
5. Kullanıcının Wi-Fi ve yönetici sırları **yerel, cihazına özel bir ilk kurulum** sırasında oluşturulmalıdır. Herkese dağıtılan bir genel imajda sabit admin/Wi-Fi şifresi bulunmamalıdır.

## 4. İlk açılış / Tihulu Kit ve adresler

**Önce bilinmesi gerekenler:**

- **Hotspot SSID:** `Tihulu Kit` (planlanan varsayılan)
- **Hotspot şifresi:** cihaz sahibi tarafından seçilir/ilk kurulumda güvenle sağlanır; bu GitHub deposunda **bulunmaz**
- **Hotspot web adresi:** `tihulu.lan` ve fallback IP `10.10.10.10` (Core servisleri gerçekten kurulduğunda)
- **Ev modemine bağlı Pi:** `tihulu.local` desteklenen mDNS ağlarında, aksi halde **modemin Pi'ye verdiği gerçek IP**
- **`tihulu.lan` ev modeminde:** yalnızca router'ın DNS'i bu ad için kayıt/alias sunarsa
- **Bilgisayara doğrudan Ethernet:** gerçek Ethernet link IP'si veya mümkünse mDNS; otomatik internet bağlantısı değildir
- **İnternet olmaması:** yüklenmiş uygulamalar ve arşivler yine yerel kullanılabilir

Ayrıntılar [Ağ ve adresler](NETWORK_ACCESS_TR.md). Hotspot'a bağlanılan telefonun kendisi internete bağlı olmak zorunda değildir; modeme bağlı olmak da Tihulu portalını otomatik internete açmaz.

## 5. Hızlı / Adım adım / Gelişmiş sihirbaz

**Hızlı Kurulum (Önerilen):**

1. Kullanıcı/oturum, güvenli Wi-Fi ve yönetici parolası oluşturma/doğrulama.
2. Türkçe/English/Deutsch arayüz dilini seçme.
3. Bir veya birkaç **ülke/bölge** seçme; bunun ayrı ayrı **harita (tile + gerçek routing grafiği + geocoder)** ve **Emergency My Countries** kapsamına nasıl yansıdığını görme.
4. Ethernet / ikinci USB Wi-Fi / PC Internet Sharing / **internetsiz devam et**.
5. Özet: **yüklü / bu kurulumda kurulacak / indirme izni bekleyen / sonra kur / uyumsuz**. İndirme büyüklükleri, boş alan, model ve kaynak lisansı, mobil veri kullanımı gösterilir.
6. Ayrı, açık seçilmiş bir Emergency izleme tercihi; “bölge seçildi” diye acil uyarı takibi sessizce **açılmaz**.
7. **Kurulumu Başlat** → güvenli Core hazırsa **Ana Ekrana Geç**. Sonradan kurulacak büyük içerikler açıkça beklemede görünür.

**Adım adım (Standart):** aynı seçenekler anlaşılır kısa ekranlarda **İleri / Geri** ile varsayılanlar seçili halde gelir. Teknik ayrıntılar zorunlu değildir.

**Gelişmiş (Custom):** tüm uygulamaları, ZIM arşivlerini, Kolibri kurslarını, dilleri, OCR/ASR/TTS paketlerini, 3 AI model profilini, harita+rota+adres veri katmanlarını, enerji, servis Hard/Background/Startup durumlarını ve NVMe disk/swap politikasını tek tek seçer.

**Varsayılan öneri**: çekirdek sistem korunur; isteğe bağlı servisler kurulmuş olsa bile Background/Startup kapalı başlayıp doğrudan kullanıcı isteğiyle çalışır. Light sistem AI ve Balanced sohbet AI yalnızca **aday varsayılanlar**dır; Pi üzerindeki gerçek testlerden geçmeleri ve kullanıcının paket indirmeyi onaylaması gerekir. Experimental Maximum 8B otomatik indirilmez.

## 6. İçerik, model ve harita indirme

**İki ayrı tamamlanma durumu** vardır:

- **Core hazır:** Home, Guide, yönetici hesabı, ağ ve paket yöneticisi çalışır; istenen arşivlerin bir kısmı henüz indirilmemiş olabilir.
- **Full Offline tamamlandı:** kullanıcı tarafından seçilmiş ve manifestte belirtilmiş Wikipedia/Kiwix, Kolibri, gerçek rota ağı/geocoder, modeller, dil paketleri ve uygulamalar mevcut ve doğrulanmış durumdadır. Hâlihazırda bulunmayan içerikler tamamlandı gösterilemez.

İndirilecek bileşenlerde resmî/uyumlu sürüm, kaynak/lisans, boyut, geçici disk alanı ve isteğe bağlı çevrimdışı USB aktarımı bulunacak. İlk projede hedeflenen **tam orijinal İngilizce ve Türkçe Wikipedia ZIM'leri** Core imajında sığmıyor diye kapsamdan çıkarılmış sayılmayacak; açıkça “sonra indir” statüsüyle korunacak.

## 7. Ağ ve bilgisayardan internet paylaşımı

Tihulu kurulumu (planlanan) kendi AP'sine ek olarak router Ethernet, ikinci USB Wi-Fi istemcisi ve doğrudan PC Ethernet bağlantısını destekleyecek. PC Ethernet kablosuna Wi-Fi interneti kendiliğinden paylaşılmaz. Windows ICS, macOS Internet Sharing veya Linux NetworkManager'ın “Shared to other computers” ayarı PC tarafında kullanıcı tarafından açılır. Pi gerçek IP/gateway/DNS durumunu gösterir; PC uyursa internet paylaşımı kesilebilir.

Bağlantı yönergeleri: [Ağ rehberi](NETWORK_ACCESS_TR.md).

## 8. HTTPS, telefon kamerası ve canlı OCR

Planlanan **Kamera → Canlı OCR** özelliğinde kullanıcı kamerayı açma izni verip görüntü alanını/metin bölgesini seçer, OCR aralığını belirler, metin anlık yenilenir, istenirse çeviri/AI açıklaması yapılır. Kamera durduğunda görüntü akışı durur; video/orijinal kare kaydetme ayrı seçenektir. Tüm cihazlarda ayrıca **Dosya Seç / Fotoğraf Çek** yolu bulunur.

**Kritik koşul:** tarayıcıdaki gerçek canlı kamera ve konum için **güvenilir HTTPS ve tarayıcı/işletim sistemi izinleri** gerekir. Basit HTTP üzerinden `10.10.10.10` adresinin açılması, kamera çalışacağı anlamına gelmez. Sertifika cihazlarda gerçekten güvenilir kılınmadan “canlı OCR hazır” denmez.

Detaylı akış: [Canlı OCR ve cihaz izinleri](LIVE_OCR_AND_PERMISSIONS_TR.md).

## 9. Servisler ve güncelleme

- **Installed** = dosyaları var; **Hard ON** = gerekirse başlayabilir; **Background OFF** = otomatik arka plan işi yok, manuel kullanım olabilir; **Startup OFF** = Pi boot'ta otomatik yüklenmez; **Runtime** gerçek çalışan durumdur.
- Kullanıcı Browser'dan Çinceden çeviri ve AI özet isterse, kurulu ve Hard ON Translator önce; ardından uygun LLM geçici açılır. Hard OFF durumda **yalnızca bu işlem / kalıcı aç / açma** ekranı gösterilir.
- Radio canlı altyazısında ASR ve gerekiyorsa Translator açılır, işi bittiğinde diğer kullanıcılar yoksa kapanır. Özgün Emergency ses kaydı varsayımsal olarak “cache” diye silinmez.
- **Update Center** gerçek kurulu/uyumlu sürümleri, kaynakları, boyutları ve seçili indirmeleri gösterecek; otomatik büyük indirmeler varsayılan olmayacak.

## 10. Doğrulama, sorun giderme, veri güvenliği

| Belirti | Önce kontrol edin |
|---|---|
| `Tihulu Kit` görünmüyor | Gerçek Tihulu Core imajı kurulu mu? Pi güç/HAT/boot durumu doğru mu? |
| `tihulu.lan` bulunamadı | Pi hotspot'unda mısınız? Router istemcisindeyseniz mDNS `tihulu.local` veya gerçek IP kullanın |
| Pi bilgisayara bağlı ama IP yok | Ethernet linki; PC DHCP/ICS açık mı? Link-local veya seçilmiş sabit IP doğru mu? |
| Kamera/OCR açılmıyor | HTTPS güvenilir mi? Tarayıcı/işletim sistemi kamera izni var mı? OCR paketi kurulu mu? |
| Wikipedia/harita bulunamadı | Kurulum özetinde gerçekten yüklenmiş mi, yoksa `Sonra kur` mu? |
| Local AI yavaş | Pi 8 GB RAM, model profilini Light'a al, başka iş/SDR kaydı ve swap baskısını kontrol et; hız garanti değil |
| Emergency uyarısı gelmiyor | Master ON, kaynak/ülke izinleri ve gerçek Internet/feed tazeliği; offline durumunu kontrol edin |

**Yedekleme:** İmaj yazmadan önce NVMe verilerini yedekleyin. Kullanıcı dosyalarını, öğrenme ilerlemesini, özgün kaydedilmiş Emergency sesini, şifreleri ve kişisel AI geçmişini güncelleme/önbellek temizleme işlemlerinde koruyun. Sıfırlama işlemleri kapsamı önce açıkça göstermelidir.

## Referanslar ve diğer belgeler

- [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
- [Raspberry Pi resmî başlama ve NVMe/boot belgeleri](https://www.raspberrypi.com/documentation/computers/getting-started.html)
- [Raspberry Pi uzaktan erişim ve `.local` mDNS](https://www.raspberrypi.com/documentation/computers/remote-access.html)
- [Tihulu ilk bilgiler](START_HERE_TR.md)
- [Ağ, adresler ve internet paylaşımı](NETWORK_ACCESS_TR.md)
- [Canlı kamera/OCR izinleri](LIVE_OCR_AND_PERMISSIONS_TR.md)
- [Kapsam ve mimari](FEATURES_AND_ARCHITECTURE_TR.md)
- [README](../README.md)
