# Telefon Kamerasıyla Canlı OCR ve Cihaz İzinleri

> **Durum (5 Kasım 2026):** Bu bir **geliştirilmesi planlanan özellik şartnamesi ve kullanıcı rehberidir**. Bu depoda şu an çalışan Tihulu canlı OCR servisi, kamera web arayüzü, sertifika kurulumu veya test edilmiş dil modeli yoktur. Gerçek performans Pi 5 8 GB, iOS Safari ve Android Chrome üzerinde doğrulanacaktır.

## Nedir?

**Canlı OCR**, telefonun (veya izinli bilgisayar webcam'inin) kamerasından **o anda görülen yazıyı** fotoğraf çekmeye gerek kalmadan belirli aralıklarla tanıyıp metin olarak göstermeyi hedefler. Kullanıcı isteğiyle bu metin Tihulu'nun aynı yerel **Translator** ve **Local AI** servislerine aktarılabilir.

Örnekler: afiş, bilgilendirme tabelası, reçete etiketi, bir kitaptaki paragraf, harita adı, yabancı dilde kâğıt üzerindeki metin veya ekrandaki yazıyı telefonla tarama. **Tıbbi/afet uyarılarında OCR/çeviri hatası olabilir; orijinal metin ve resmî kaynaklar korunur.**

## Kullanıcı deneyimi (hedef)

1. Tihulu Home → **OCR / Kamera** ya da Browser/PDF/Files/Translator içinde **Kamerayla Tara → Canlı OCR**.
2. Önce **“Telefon kamerasını kullanmak istiyor musunuz?”** açıklaması. Kamera izni yalnızca kullanıcının eylemi sonrasında tarayıcı/OS tarafından sorulur. İzin verilmezse **Fotoğraf Çek / Galeriden Seç / Dosya Seç** alternatifleri.
3. Kameranın **ön/arka seçimi**, varsa fener/odak/zoom yeteneği, ekran döndürme, otomatik/manual dil, taranacak bölge (ROI), stabilizasyon/kontrast rehberi, taramayı başlat/durdur düğmeleri.
4. Kullanıcı **“Canlı OCR Başlat”** der; bir defa fotoğraf göndermek yerine seçilmiş görüntü alanından aralıklı kareler yerel OCR motorunda işlenir. Metin kutuları, seçili tanınan metin, güvenilirlik/kalite uyarısı, son işlenen kare ve bekleme durumu gösterilir.
5. Değişen kareleri sürekli aynı metin gibi eklememek için **temizle**, **kilitle/dondur**, **bu kareyi işle**, **yeni satır ekle** modları sunulur. Zayıf sonuçlar için kullanıcı ham OCR metnini düzeltir.
6. Sonraki ayrı eylemler: **Metni Kopyala**, **Paylaş / Dosyaya Kaydet**, **Çevir (TR/EN/DE ve kurulu diğer diller)**, **AI ile Özetle / Açıkla / Soru Sor**, **PDF/Not olarak kaydet** (ilgili entegrasyon kuruluysa). Kaynak görüntünün ve OCR sonucunun tarih/belge bağlantısı isteğe bağlı.
7. **Durdur / Kapat** kamera izini kapatır, seçilen OCR/Translator/LLM görevleri sırayla güvenle sonlandırılır; başka kullanıcı yoksa RAM'den çıkarılır. **Orijinal video veya kareler varsayılan olarak kaydedilmez**, açık kaydetme izni istenir.

## Gerçek zamanlı nasıl çalışır?

- Web istemcisi `navigator.mediaDevices.getUserMedia({video: ...})` üzerinden **o anda açık** kamera akışını alır; kamera telefonda kalır.
- OCR için **tüm videoyu sürekli NVMe'ye kaydetmek yerine** sınırlı, görünür ve kullanıcı denetimli kare/ROI alınır; ağ ve Pi 5 yüküne göre tarama aralığı uyarlanır. Örnek deneysel hedef **0.5–2 kare/saniye** olabilir, **garanti edilen FPS/latans değildir**; gerçek benchmark ile ayarlanır. Trafik sıkıştığında kare atlamak ve kuyruk sınırı koymak, devamlı her kareyi yığmaktan güvenlidir.
- Eğer Pi'de etkin OCR işçisi kullanılıyorsa yalnızca gerekli kareler **yerel, kimliği doğrulanmış HTTPS** üzerinden Pi'ye gönderilir. Gerekli OCR dil paketi yoksa gösterilir ve Wizard/Update Center üzerinden ayrı indirme/USB import seçeneği sunulur; metin uydurulmaz.
- Bazı uygun cihazlarda **istemci içi OCR** seçeneği de ileride değerlendirilebilir; bu destek **garanti değildir**. Pi sunucusuna işlenen kare ve ara metin saklama, silme veya RAM'de tutma politikası ayrı gösterilir.
- OCR için adaylar Tesseract/benzeri ARM64 uyumlu motorlar ve gerçek dil paketleridir. `tur`, `eng`, `deu` ilk adaylar; Çince, Arapça, Rusça vb. için ayrı uygun trained-data ve Translator paketi gerekir. El yazısı, eğik/çok küçük metin, hareket ve düşük ışıkta sonuçlar güvenilmez olabilir.
- Üst üste kaynak kutuları, takip/kararlı metin, istenirse çeviri overlay'i, yüz/kişisel veri gizliliği, uzun metin birleştirme ve koordinat dönüşümü gerçek cihaz testlerinden sonra uygulanır; **“sınırsız AR çevirisi hazır”** iddiası değildir.

## Offline çeviri ve AI entegrasyonu

İki ayrı basamak vardır:

1. **OCR** — kamerada görünen yazıyı metne çevirir. **Çeviri değildir.**
2. **Translator** — yazının dilini TR/EN/DE gibi kurulu hedef dillere dönüştürür.
3. **Local AI** — kullanıcı **ayrıca istediğinde** bu tanınmış/çevrilmiş metni özetler, açıklar veya sorulara kaynak bağlamıyla yanıt verir.

Yabancı dilde tabela örneği: Kamera → **Çince OCR** → **Çince-Türkçe/İngilizce Translator** → istenirse **Local AI**. Her aşamanın eksik model/izin durumu ayrı görünür; bir çeviriyi desteklenmeden uydurma “özet” üretilmez.

**Service Manager kuralları (Aşama 4 tasarımında onaylanmış):**

- OCR/Translator/AI **Background OFF** veya **Startup OFF** fakat **Hard ON + kurulu** ise *kullanıcı canlı OCR'yi başlattığında* gerekli işçiler geçici açılır; başka görev kalmayınca kapanır.
- OCR/Translator/AI işçisi **Hard OFF** ise **“Yalnızca bu işlem için aç / Kalıcı aç / Açma, kullanılabilen işlevlerle devam et”** seçim ekranı gösterilir. İzinsiz Hard OFF aşılmaz.
- Aynı OCR/Translator işçisi başka Browser, PDF veya Radio görevinde kullanılıyorsa bu görüntüden çıkmak işçiyi erken sonlandırmaz.
- Kaynak görüntü ve kayıtlar ayrı bir **kullanıcı kaydetme/onay tercihi** ile saklanır. Varsayılan **kalıcı kare/video kaydı yok**.

## Kamera ve dosya izinleri

| İşlem | Kullanıcı eylemi / izin |
|---|---|
| Canlı kamera aç | Kamera başlat seçimi + işletim sistemi/tarayıcı kamera izni |
| Ön/arka kamera | Cihaz/browser destekliyorsa görünür seçim |
| Fotoğraf çek | Kullanıcının `Fotoğraf çek` seçimi, standart kamera capture veya kamera preview |
| Galeriden fotoğraf seç | Kullanıcı kontrollü **Galeri / Fotoğraflar** seçici |
| Telefon belgesi seç | **Dosya Seç**; bütün telefon dosyalarına gizli erişim yok |
| Bilgisayarda belge | **Sürükle-bırak** veya **Dosya Seç** |
| OCR çalıştır | İşlemin amacı, yerel veri işleme durumu, uygun OCR dil paketi |
| Çeviri/AI | Ayrı kullanıcı isteği, gerekli model ve Hard OFF izni |
| Fotoğraf/video/metin kaydet | Ayrı kaydetme ve saklama konumu onayı |
| Canlı konum | **Kullanıcının** geolocation/GPS izni; OCR kameraya bağlı diye otomatik verilmez |

**İzin her istemci cihazı ve tarayıcı origin'ine özeldir**. iPhone'da kameraya izin vermek bilgisayarın webcam'ini açmaz. Tihulu Pi'nin bir Ethernet kablosuyla bilgisayara bağlı olması, Pi'ye bilgisayarın kamerasını veya tüm dosyalarını otomatik açmaz.

## HTTPS ve neden kritik?

MDN'ye göre `getUserMedia()` ve Geolocation için **secure context** gerekir. `https://tihulu.lan`, `https://tihulu.local` veya özel LAN IP'sini açmak **tek başına yeterli değildir**: sertifika/hostname ve kullanıcı cihazının bu sertifikaya güvenmesi de düzgün yapılandırılmalıdır. Kendi imzalı ve tarayıcının güvenmediği sertifika otomatik olarak kabul edilmez.

- **Hotspot:** `tihulu.lan` ve `10.10.10.10` üzerinden doğru ağ; HTTPS sertifika çözümü test edilmediyse canlı kamera düğmesi çalışmayabilir.
- **Router LAN:** `tihulu.local` mDNS destekliyse veya gerçek Pi DHCP IP ile giriş; aynı HTTPS trust sorunu ayrı çözümlenir.
- **Doğrudan PC Ethernet:** bilgisayarın browser'ından Pi direct-link IP/host, trusted origin sertifikası.
- Tarayıcının kamera izni **reddedilirse** tekrar tekrar tarama yapma; nedenini açıklama ve dosya/fotoğraf seçici sunma.
- Kamera açılışından sonra **Durdur** ile `MediaStreamTrack.stop()` hedeflenir; bağlantı kopması/kilitleme/uygulama arka plana gitmesi de güvenli kapanma gerektirir. Sürekli arka plan kamerayı kullanma yok.

Resmî tarayıcı referansları:
- [MDN — MediaDevices.getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- [MDN — input type=file](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/file)
- [MDN — capture=user/environment](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/capture)
- [MDN — Geolocation](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation_API)

## Gerçek cihazda kabul testleri

- iPhone Safari ve Android Chrome üzerinde güvenilir HTTPS ile ön/arka kamerayı kullanıcı izniyle aç, ROI seç, Türkçe/Almanca/İngilizce metni okunaklı tanı ve **Durdur** sonrası kamera akışı durdur.
- Kamera reddedilince **Dosya Seç / Galeri / Kamera fotoğrafı** alternatifleri ve kalıcı izinsiz kayıtsız durdurma.
- Çince tabela/kâğıt: Çince OCR + uygun dil paketi → Türkçe/İngilizce Translator → açık kullanıcı isteğiyle AI özeti; eksik pakette sahte yanıt yok.
- Pi 5 8 GB CPU/RAM sıcaklık ve ağ gecikmesi altında adaptif OCR kare hızı. Aynı anda gerçek Radio/Emergency kaynak kaydı varsa korunmalı, tarama gerekirse yavaşlatılmalı.
- Kötü ışık, eğik/bozuk görüntü, çok satırlı metin, hareket, farklı alfabeler ve kişisel/mahrem belgeler; orijinal koruma, işlenen/kaydedilen verileri ayırma.
- Hotspot/router ikinci USB Wi-Fi/router Ethernet/doğrudan PC Ethernet üzerinden aynı canlı OCR; HTTPS/gizlilik/izin tekrarı.
- Webcam sahibi bilgisayarın tarayıcısında Tihulu açık değilse o bilgisayar kamerasını başka telefondan izinsiz kullanamama.
- Kaydetmeden kapanınca videonun/veri karelerinin disk/backup/AI proje geçmişinde sessiz kalmaması; kullanıcı bilerek `Kaydet` seçtiğinde sadece belirtilen kapsamın saklanması.

## Diğer rehberler

- [İlk Açılış](START_HERE_TR.md)
- [Kurulum](INSTALLATION_TR.md)
- [Ağ ve Erişim](NETWORK_ACCESS_TR.md)
- [Özellikler ve Mimari](FEATURES_AND_ARCHITECTURE_TR.md)
- [Ana README](../README.md)
