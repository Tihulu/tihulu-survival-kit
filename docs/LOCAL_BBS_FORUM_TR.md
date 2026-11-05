# Tihulu Local BBS / Forum — isteğe bağlı, henüz plan

**Neden:** Teletekst ve RDS/DAB metin yayınları **tek yönlü**. Tihulu Kit hotspot'una bağlanan iki telefon/PC, ek anten veya internet olmadan **yerel web BBS / forum / mesaj** sistemiyle konuşabilir. Bu hizmet henüz yazılmadı veya Raspberry Pi'de çalışmıyor.

- Home > Haberleşme > Yerel Forum: konu başlıkları ve cevaplar; yerel bireysel/grup mesajları; metin ağırlıklı, ekler kapalı varsayılan; Türkçe/Almanca/İngilizce dil seçenekleri.
- Kullanıcının onayladığı cihaz/hesaplar. Misafirler varsayılan olarak diğer üyelerin özel mesajlarını göremez. Şifreleme, auth, ACL, CSRF ve uygun modern HTTPS uygulanmadan gerçek servisi açma.
- Internet bağımsız, yalnızca **Pi'nin kapsadığı yerel Wi-Fi ağı**. Uzak kişilere mesaj taşımaz; Meshtastic, CB Packet, APRS ya da Winlink gateway'i olduğunu iddia etmez.
- **Hard ON / Background OFF / Startup OFF** varsayılan; sayfa açılınca isteğe bağlı servis açılır, son kullanıcı ayrılınca kaynakları bırakır. Kendi forum oturumunu açık tutmak isteyen kullanıcı arka planı ayrıca etkinleştirebilir. Cihazda aktif forum işçisi varsa diğer kullanıcıların pencerelerini kapatmak bunu kesmemelidir.
- Haber akışının 24 saat sonra silme kuralı **forömdeki kullanıcı mesajlarını otomatik silmez**. Forum mesajları kullanıcı/sahibin belirlediği saklama süresine göre tutulur; silme hakları ve yedekleme ayrı kurallar gerektirir.
- SQLite temel veri saklama; veri tabanı ve yüklenen dosyalar hesap izolasyonu ve yetkili silme ile yönetilecek. Tekrarlanan şüpheli trafik, kota, anti-spam ve kriz sırasında erişim izolasyonu.
- Gelecekte isteyen kişi Meshtastic/packet BBS ile ayrı **manuel, izinli ve donanım/yerel mevzuat denetimli** köprü oluşturabilir; **varsayılan olarak mesajlar dışarı iletilmez**.
- Stage4 katalog kaydı `local_bbs` yalnızca mantıksal, `installed=False`; hiçbir çalışan forum sunucusu kurulmadı.
