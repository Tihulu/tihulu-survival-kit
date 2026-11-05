# Tihulu Stage 4 — Deneysel isteğe bağlı servis yöneticisi

**Durum (5 Kasım 2026):** Bu dalda yalnızca Python standart kütüphanesiyle çalışan, birim testleri olan **politika/lease çekirdeği** bulunur. **Raspberry Pi'ye kurulu değildir.** Web arayüzü, kimlik doğrulamalı API, gerçek systemd servis eşleştirmeleri, kurulum imajı, Kiwix/Kolibri/LLM/SDR entegrasyonu ve gerçek RAM ölçümleri hâlâ yapılmalıdır. Haberleri, yayınları ve modelleri şu an indirmez veya çalıştırmaz. Ana Tihulu Home/hotspot mevcut değildir.

## Kararlar ve davranış

* **Hard ON/OFF**, **Background ON/OFF**, **Startup ON/OFF**, kurulu olup olmama ve **gerçek çalışma durumu** ayrıdır. Varsayılan optional kurulu modül ilk kullanıcı talebinde başlayabilir; Background OFF kendiliğinden polling/AI/model ısınması başlatmaz.
* **Hard OFF** sessizce geçilemez. Ayrı bir **doğrulanmış sahip onayı**yla tek göreve ve gerekli worker kimliklerine bağlı, 1 saatten kısa tek kullanımlık izin verilebilir. Kalıcı Hard OFF değişmez. Alternatif olarak Hard ON kalıcı açılır ya da kullanıcı reddeder; ileride mobil bağımlılık diyalogu bunu uygulayacak.
* **Ortak worker leasing**: Browser çeviri, Radio altyazısı ve başka sekmeler aynı Translator/ASR/LLM servisini tekrar başlatmaz. Son görev serbest bırakıldığında uygun süre geçince worker durdurulur. Sadece sekme kapanması server-owned kayıt/uzun işlemi serbest bırakmaz.
* **Emergency Monitor** için kurulumda **açık sahip seçimi** gereklidir; ilk değer belirtilmemiştir. Hard OFF/kapalı izleme yeni bildirim üretmez. Önceden kaydedilen orijinal ses ve kullanıcı dosyaları bu modül tarafından silinmez.
* **Korunan temel servisler** (Pi OS, NVMe, Tihulu Kit AP, DNS/DHCP, portal, Guide, kimlik doğrulama, recovery) optional katalogda yoktur. Başlatma/durdurma adapter'ı yalnızca kodda açıkça eşlenen `tihulu-*.service` **kullanıcı** birimleriyle çalışabilir. Kök/system servislerine dokunmaz.
* Haber akışının **24 saatlik saklama / 30 MB önbellek** politikası ayrı News storage bileşeninin sorumluluğunda olacak; bu paket haber arka plan işini sadece açık izinle başlatabilir, henüz içerik temizleme motoru değildir.
* Enerji kaynak yönetimi: Kod gerçek CPU/RAM/PSI ölçmez, fiktif Watt veya hız değerleri iddia etmez. Pi5 8 GB üzerinde gerçek admission/scheduler, UI, kayıttan veri kaybetmeden durdurma ve servis crash recovery testleri gereklidir.
* **Bir işin active lease'i** kullanıcı sekmeden çıkınca korunabilir; kamera/mikrofon gibi tarayıcı-kaynaklı yakalama işleriyse arka plan sekmede devam edemez. Her işin kendine ait iptal/Task Center UI'si henüz yoktur.

## Nasıl test edilir?

```bash
python3 -m unittest discover -s tests -v
```

## Kullanım örneği (donanımsız test adapter'ıyla)

```python
from tihulu_runtime import Module, ServiceManager

class Fake:
    def start(self, module_id): print("start", module_id)
    def stop(self, module_id): print("stop", module_id)

m = ServiceManager([Module("translator", installed=True)], Fake())
m.acquire("translator", task_id="browser-translate-1", owner_id="owner")
m.release("browser-translate-1", owner_id="owner")
m.sweep_idle()
```

`tihulu_runtime/catalog.py` aynı politikayı News, Kiwix, Kolibri, Maps/Router, AI, Translator/OCR/ASR/TTS, Browser, Radio, TV, Emergency, Files/Nextcloud, PDF/Office/Media, Subtitle Studio, NOMAD ve Update Checker'a uygulayacak **mantıksal kimlikleri** listeler. `installed=False` varsayılanı özellikle korunmuştur: çalışmayan bir bileşen yanlışlıkla çalışıyormuş gibi gösterilemez.

**Güvenlik entegrasyonu:** Gerçek API geldiğinde `owner_verified` yalnızca sunucu tarafından doğrulanmış oturum/CSRF/rol ve allowlist denetimi sonrası set edilmeli; istemciden `owner_verified=true` alanı kabul edilmemelidir. Ayrı yetkili iş yöneticisi, indirme izinleri ve korumalı kaynaklar olmadan bu deneysel kütüphane ağdan erişilebilir hâle getirilmemelidir.

İlgili özel, onaylı tasarım: Stage 4 Checkpoint 043, `plan/55`, `plan/57`, `plan/58` ve çok sekmeli iş modeli `plan/70`.
