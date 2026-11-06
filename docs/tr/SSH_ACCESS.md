# SSH ve Terminal Erişimi — Tihulu Survival Kit

> **Proje durumu (6 Kasım 2026):** Bu belge ileride sunulacak çevrimdışı Guide ve Setup Wizard için hazırlanmış içeriktir. Çalışan bir Tihulu imajının veya SSH servisinin yayımlandığı anlamına gelmez. Sıradan Raspberry Pi OS Lite üzerinde `tihulu-kit` kullanıcısı kendiliğinden oluşmaz.

## Planlanan SSH hesabı

| Ayar | Kullanım |
|---|---|
| Linux / SSH kullanıcı adı | `tihulu-kit` — yalnızca kişisel Tihulu kurulumunda hesap gerçekten oluşturulduysa |
| İlk SSH parolası | **Kullanıcının kendi cihazında özel olarak atadığı parola**; ortak imajda veya GitHub'da yayımlanmaz |
| SSH servisi | Kullanıcı tarafından etkinleştirilebilir; gerçekten açılmadan port 22 çalışıyor varsayılmaz |
| Web yönetici hesabı | Linux SSH hesabından ayrı kimlik ve yetkilendirme |
| Wi-Fi şifresi | `Tihulu Kit` hotspot'unun ayrı parolası |

Cihaz sahibi kendi seçtiği ilk SSH parolasını **yerel Image Builder veya ilk kurulumda** güvenli biçimde atayabilir. Parola kamuya açık GitHub kaynaklarına, paylaşılan imaja veya Guide içeriğine düz metin olarak yazılmaz. Benzersiz ve güçlü parola ya da SSH anahtarı önerilir. Linux'ta parola genelde yalnızca tek yönlü doğrulama özetiyle saklandığından mevcut parola Guide'da geri okunamaz.

## Bağlantı komutları

Gerçek Tihulu kurulumu ve SSH servisi **etkinleştirildikten sonra**:

```sh
# Bilgisayar Pi'nin "Tihulu Kit" Wi-Fi ağına bağlıyken:
ssh tihulu-kit@tihulu.lan
# Yalnızca Pi hotspot'undaki alternatif:
ssh tihulu-kit@10.10.10.10

# mDNS/Avahi çalışan ev ağında:
ssh tihulu-kit@tihulu.local

# Router ya da doğrudan PC Ethernet bağlantısında:
ssh tihulu-kit@<pi-gercek-ip-adresi>
```

Son komuttaki örnek yeri Pi'nin o ağdaki gerçek IP adresiyle değiştir. `10.10.10.10` yalnızca Pi'nin kendi hotspot IP hedefidir; ev router'ında geçerli olmak zorunda değildir. `tihulu.lan` router tarafından otomatik tanınmaz.

Komut sonrasında istenen parola, cihazda yerel olarak atanmış **Linux/SSH parolasıdır**. Wi-Fi veya web yönetici parolası değildir. Parolayı komut satırına, URL'ye ya da GitHub'a yazma. İlk bağlantıda SSH sunucu anahtarı parmak izini güvenilir başka bir yolla doğrulamadan kabul etme.

## SSH'yi açma, kapatma ve parolayı değiştirme

**Planlanan menüler:** `Guide > Ağ ve SSH`, `Settings > Security > SSH / Remote Access`.

- SSH'nin gerçek **Açık / Kapalı / Kullanılamıyor** durumunu, kullanılabilir ağ adreslerini ve hesabın kurulu olup olmadığını göster.
- Yetkili kullanıcı SSH'yi açıp kapatabilsin, şifreyi değiştirebilsin, SSH açık anahtarları ekleyip silebilsin ve erişimi güvenilir yerel ağlarla sınırlayabilsin.
- Paylaşılan Tihulu imajında herkesin bildiği sabit parola bulunmasın. İnternete açık SSH varsayılan olmasın.
- SSH hesabıyla giriş yaptıktan sonra `passwd` komutu, o hesabın parolasını etkileşimli olarak değiştirir. Parola unutulursa doğrulanmış yönetici veya fiziksel kurtarma süreci gerekir.
- SSH parolasını değiştirmek web yönetici hesabının veya hotspot'un parolasını değiştirmez.

**Normal kullanım için SSH zorunlu değil:** Gerçek telefon-hazır Tihulu Core kurulduğunda Home ve kurulum sihirbazı tarayıcıdan açılabilecek.

## Sorun giderme

1. **İsim çözülmüyor:** Doğru Wi-Fi/LAN bağlantısını ve gerçek IP adresini kontrol et.
2. **Connection refused:** SSH servisi kapalı veya güvenlik duvarı izin vermiyor olabilir.
3. **Permission denied:** `tihulu-kit` hesabının gerçekten kurulduğunu doğrula; Linux hesabına ait parolayı kullan.
4. **Host key changed:** Uyarıyı sorgulamadan kaldırma; sistem yeniden yazıldı mı ve anahtar gerçekten değişti mi doğrula.
5. **AI HAT sonrası Pi açılmıyor:** Bu SSH hatası değildir; güç kapalıyken doğrulanmış NVMe/PCIe boot düzenine dön. [AI HAT yükseltme rehberi](AI_HARDWARE_UPGRADES.md).

Bkz. [Ağ ve Erişim](NETWORK_ACCESS.md), [Başlangıç](START_HERE.md), [Kurulum](INSTALLATION.md).
