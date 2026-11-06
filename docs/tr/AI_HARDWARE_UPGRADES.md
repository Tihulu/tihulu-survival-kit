# Kurulumdan sonra AI HAT+ 2 yükseltmesi — açılışta algılama ve mod değiştirme

> **Durum (6 Kasım 2026):** Bu, Stage 10 incelemesine eklenen bir gereksinimdir; çalışan Pi donanım algılama servisi veya yayımlanmış kurulum yazılımı değildir.

## Sonradan HAT takıldığında

1. Önce Raspberry Pi'yi **tamamen kapat**. Pi5'in NVMe boot için kullandığı PCIe bağlantısı ile AI HAT+ 2 arasında gerçek bir donanım çakışması olabilir. Boot SSD'sini çıkarınca sistem açılmıyorsa yazılım yeni HAT'i algılayamaz; önce güvenli depolama/boot düzeni doğrulanmalı.
2. Fiziksel uyumluluk, güç ve soğutma kontrolünden sonra HAT'i takıp Pi'yi başlat.
3. **Her başarılı açılışta** sistemin küçük bir donanım keşif görevi Pi/PCIe/Hailo, bağlı SSD'ler ve sürücü durumunu önceki doğrulanmış kayıtlarla karşılaştıracak. Yeni HAT'i görmek **otomatik driver indirme, LLM başlatma, model seçme veya mod değiştirme** anlamına gelmez.
4. Yeni HAT bulunduğunda yetkili kullanıcıya **Yeni AI donanımı algılandı** bildirimi gösterilecek. `Settings > Hardware` ve `AI Hardware & Model Setup` bölümünden yeniden yapılandırma veya daha sonra hatırlatma seçilecek.
5. Ayrı durumlar gösterilecek: **Donanım algılandı**, **Sürücü/runtime kurulu**, **Uyumlu NPU modeli kurulu**, **Gerçek çalıştırma testini geçti**, **Aktif AI modu**.
6. `Software & Update Center` eksik Hailo sürücülerini, runtime ve uyumlu modelleri gerçek kaynak/boyut/lisans bilgisiyle listeleyecek. Kullanıcı onayı olmadan indirme veya sürücü/firmware güncellemesi yapılmayacak; yeniden başlatma gerekiyorsa bildirilecek.
7. Kullanıcı **CPU Local**, **NPU Local**, açık onaylı **özel ağdaki uzak AI** veya **Auto / tercih edilen** modları seçebilecek. Daha önce çalışan CPU modeli korunacak; NPU modeli ile GGUF aynı formatmış gibi varsayılmayacak.
8. HAT güç kapatıldıktan sonra çıkarılırsa, sürücü çalışmazsa veya modelin bulunduğu SSD ayrılırsa, sistem orijinal verileri silmeyecek; mevcut ve çalışabilir CPU modeli varsa onu teklif edecek. Hotspot, Guide, Radio ve diğer AI dışı modüller korunacak.

## Planlanan Guide menüleri

`Guide > Donanım yükseltmeleri > AI HAT+ 2`, `Settings > Hardware > Değişiklikleri Algıla`, `AI Hardware & Model Setup > Yeniden Kontrol Et`, `Update Center > Donanım bağımlılıkları`.

Donanım değişikliğinde tüm ilk kurulum sihirbazı yeniden başlatılmayacak. En son algılama zamanı, sürücü ve model uygunluğu, aktif/tercih edilen mod ve hata/rollback durumu ayrı gösterilecek.

## Test zorunluluğu

Gerçek Raspberry Pi 5 üzerinde HAT takmadan ve taktıktan sonra boot; NVMe/PCIe uyumluluğu; gerçek Hailo model yükleme; kullanıcının onayıyla güncelleme ve reboot; HAT çıkarılınca CPU fallback; kayıtların ve SSD verilerinin korunması; telefon arayüzü, çevrimdışı mod ve güvenli kurtarma ayrıca doğrulanmalı. Simülasyon testi gerçek donanım testi değildir.
