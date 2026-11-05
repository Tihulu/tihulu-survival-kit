# Başlangıç Rehberi — Önce Bunları Bilin

> **Proje durumu (5 Kasım 2026):** Tihulu Survival Kit geliştirme/planlama aşamasındadır. Çalışan Tihulu imajı, otomatik kurucu, yerel web portalı ve cihaz-içi Guide henüz yayımlanmadı. Bu sayfa **hedeflenen kullanıcı deneyimini** ve güvenli hazırlık bilgilerini açıklar; mevcut bir kurulum bağlantısı gibi değerlendirmeyin.
>
> **Güvenlik:** Bu açık depoda hiçbir gerçek Wi-Fi, yönetici, Nextcloud veya Hugging Face parolası/tokeni tutulmaz. Yayınlanacak genel imajda ortak/sabit bir yönetici parolası bulunmayacaktır.

## Tihulu'ya nasıl bağlanacağım?

Tihulu Core kurulup ilk açılış yapılandırması tamamlandığında planlanan Wi-Fi/ağ adresleri:

| Cihazınız nereye bağlı? | Tihulu'nun ağ bağlantısı | Öncelikli adres | Alternatif |
|---|---|---|---|
| Pi'nin kendi Wi-Fi ağı **Tihulu Kit** | Dahili Pi Wi-Fi hotspot (internet gerektirmez) | `http(s)://tihulu.lan` | `10.10.10.10` |
| Evinizin modem/router ağı | Pi, modeme **Ethernet** kablosu ile bağlı | `http(s)://tihulu.local` (mDNS çalışırsa) | Modemin Pi'ye verdiği **gerçek yerel IP** |
| Evinizin modem/router ağı | Pi, modeme **ikinci USB Wi-Fi adaptörü** ile bağlı | `http(s)://tihulu.local` (mDNS çalışırsa) | Modemin Pi'ye verdiği **gerçek yerel IP** |
| Bilgisayarınız doğrudan Pi'ye bağlı | Pi'nin Ethernet kablosu doğrudan PC'ye bağlı | `http(s)://tihulu.local` (mDNS/link çalışırsa) | Kurulan doğrudan bağlantının **gerçek Pi Ethernet IP'si** |

**Önemli ayrıntılar:**

- `Tihulu Kit` **planlanan varsayılan SSID'dir**, şifre değildir. Şifre cihaz sahibi tarafından **güvenli ve cihazına özgü** oluşturulacak/önceden kişiselleştirilmiş imajdan sağlanacaktır. Gerçek şifre asla GitHub README'sinde yazılmayacak.
- `tihulu.lan`, Pi'nin **kendi hotspot DNS'i** tarafından çözümlenecek. Aynı adın ev modeminin Wi-Fi'sinde otomatik çalışması **garanti değildir**; router üzerinde yerel DNS kaydı gerekiyorsa Guide açıklayacak.
- `tihulu.local`, **mDNS/Avahi** destekli cihaz ve ağlarda çalışır. Konuk Wi-Fi, istemci izolasyonu, farklı VLAN veya mDNS engeli varsa Pi'nin gerçek yerel IP'sini kullanın.
- `10.10.10.10` **Pi hotspot IP'sidir**. Ev modemi üzerindeki Pi IP'si olduğu varsayılmamalıdır.
- `http(s)://` ifadesi **kullanıma açılacak ve güvenilirliği yapılandırılmış HTTPS varsa onu, temel/onboarding erişimi gerekiyorsa uygun HTTP bağlantısını** temsil eder; belirli bir şemanın çalıştığı henüz garanti değildir.
- Kamera, mikrofon ve GPS/konum gibi tarayıcı özellikleri çoğunlukla **güvenilir HTTPS (secure context)** ister. Tek başına HTTP IP ile sayfa açılabilirken canlı OCR için kamera izni alınamayabilir; bağlantı ve sertifika kurulum adımları [Ağ rehberinde](NETWORK_ACCESS_TR.md).

## İlk açılışta sırayla ne olacak? (hedeflenen davranış)

1. Yayınlanmış, imzası/hash'i doğrulanmış **Tihulu Core** veya Full Offline imajını NVMe'ye yazın. **Şu anda böyle bir yayımlanmış imaj yok;** Raspberry Pi OS Lite tek başına Tihulu portalını oluşturmaz.
2. Pi 5'e NVMe/HAT, soğutma ve uygun güç kaynağını bağlayıp açın. Core yüklüyse **Tihulu Kit** hotspot'unu arayın. Alternatif olarak Pi'yi modeme Ethernet/USB Wi-Fi istemcisi ile veya doğrudan bilgisayara Ethernet ile bağlayın.
3. Ağa bağlanıp o arayüzün **doğru** Tihulu adresini tarayıcıda açın.
4. İlk **yönetici hesabını** oluşturun, hotspot şifresini/SSID'yi kontrol edin. Hotspot şifresi ile yönetici parolası **farklı** olmalıdır.
5. **Hızlı Kurulum (önerilen)**, **Adım adım (Next/Next)** veya **Gelişmiş** seçin. Dil (TR/EN/DE), ülke/bölge, harita alanı ve Emergency takibi tercihlerini belirtin.
6. Kurulum özeti size neyin **yüklü**, **indirilecek**, **sonradan kurulacak** veya **desteklenmediğini** açıkça göstersin. Büyük Wikipedia ZIM, harita/rota ağı ve LLM dosyaları izinsiz indirilmesin. İnternetsiz başlamak mümkün olsun.
7. Temel sistem hazırsa **Tihulu Home**'a geçin. Eksik paketleri daha sonra **Software & Update Center** üzerinden yönetin.

## İlk anda hangi düğmeleri göreceğim? (planlanan Guide)

- **Ana Ekran:** Kurulu/aktif uygulamalar, bağlantı ve disk durumu.
- **Ağ:** Tihulu Hotspot, ikinci Wi-Fi (modem istemcisi), Ethernet (modem veya doğrudan bilgisayar), gerçek erişim IP'leri ve kopyalama.
- **Kurulum:** Hızlı/Adım adım/Gelişmiş modları ve daha sonra kur.
- **Uygulamalar:** Kiwix/Wikipedia, Kolibri, Maps, Emergency, Radio, Browser, Local AI, Translator/OCR, Files, PDF, Office, Media Player (kurulu paketlere bağlı).
- **Service/Startup/Energy Manager:** Hard ON/OFF, Background ON/OFF, Startup ON/OFF, otomatik uyku ve enerji.
- **Dosya/Kamera:** Telefonda `Dosya seç`, galeriden seçim ve `Kamerayla Tara / Canlı OCR`; bilgisayarda dosya sürükle-bırak; **cihaz/tarayıcı izinleriyle**.

## En çok sorulacak sorular

**Wi-Fi şifresini nereden öğreneceğim?** Cihaza özgü ilk yapılandırma ekranı/kişiselleştirilmiş yerel kurulum kaydından. Bu sayfa ve açık GitHub deposu **bilerek** şifre içermez. Şifreyi daha sonra **Ayarlar → Ağ → Tihulu Hotspot** üzerinden değiştirebilme hedefi vardır.

**`tihulu.lan` çalışmıyor.** Önce **Tihulu Kit** ağına gerçekten bağlı olduğunuzu kontrol edin. Aynı router Wi-Fi'sindeyseniz `tihulu.local` veya router'ın verdiği IP'yi deneyin. Daha ayrıntılı sorun giderme: [Ağ ve erişim](NETWORK_ACCESS_TR.md).

**İnternet olmadan çalışır mı?** Yüklenmiş içerik ve uygulamalar evet. Henüz indirilmemiş Wikipedia/harita/LLM içerikleri çalışıyormuş gibi gösterilmeyecek.

**Telefonun kamerasından canlı metin tanıma?** Planlandı. Kameradan akan karelerin belirli aralıklarla OCR işlenmesi, metnin düzeltilmesi ve istenirse Translator/Local AI'a geçirilmesi, görüntü saklamanın ayrı izne tabi olması hedefleniyor. [Canlı OCR ve izinler](LIVE_OCR_AND_PERMISSIONS_TR.md).

**Kamera neden açılmıyor?** Tarayıcının kamera izni, cihazın kendi kamera izni ve güvenilir HTTPS bağlantısı gerekebilir. Alternatif olarak fotoğraf çekip **Dosya seç** ile gönderme akışı kullanılacak.

**Bu bir afet uyarı alıcısı mı?** Yalnızca kurulu, doğru yapılandırılmış ve yetkilendirilmiş kaynaklar takip edildiğinde bilgi sağlayabilir; resmî acil servislerin veya güvenilir uyarı kanallarının yerine geçmez. İnternet, kaynak ve anten kısıtları açıkça gösterilir.

## Devamı

- [Kurulum rehberi (adım adım ve imaj türleri)](INSTALLATION_TR.md)
- [Ağ rehberi, adresler, Wi-Fi ve doğrudan PC Ethernet](NETWORK_ACCESS_TR.md)
- [Canlı kamera OCR ve cihaz izinleri](LIVE_OCR_AND_PERMISSIONS_TR.md)
- [Uygulamalar, içerik ve sistem mimarisi](FEATURES_AND_ARCHITECTURE_TR.md)
- [Ana README](../README.md)
