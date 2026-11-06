# SSH- und Terminalzugang — Tihulu Survival Kit

> **Projektstatus (6. November 2026):** Dies ist ein Entwurf für die spätere Offline-Guide-App und den Einrichtungsassistenten. Es gibt noch kein veröffentlichtes Tihulu-Image oder garantiert aktives SSH. Raspberry Pi OS Lite richtet den projektspezifischen Benutzer nicht automatisch ein.

## Geplantes SSH-Konto

| Einstellung | Vorgabe |
|---|---|
| Linux-/SSH-Benutzername | `tihulu-kit`, sofern bei der persönlichen Installation angelegt |
| Erstes SSH-Passwort | Vom Besitzer **lokal und privat** eingerichtet; niemals als Klartext im öffentlichen Repository oder einem gemeinsamen Image |
| SSH-Dienst | Nur aktiv, wenn tatsächlich eingerichtet und vom Besitzer freigegeben |
| Web-Administratorkonto | Eigenständige Anmeldung |
| WLAN-Kennwort | Separates, gerätespezifisches Kennwort für das Netz `Tihulu Kit` |

Ein persönlich gewähltes Passwort wird im lokalen Image Builder oder bei der Erstinstallation eingegeben. Verwende ein starkes einzigartiges Passwort oder einen SSH-Schlüssel. Vorhandene Linux-Passwörter lassen sich aus den gespeicherten Prüfsummen nicht im Klartext anzeigen.

## SSH-Verbindung

Wenn Pi-Netzwerk und SSH-Dienst tatsächlich funktionieren:

```sh
# Über das eigene WLAN des Pi ("Tihulu Kit"):
ssh tihulu-kit@tihulu.lan
ssh tihulu-kit@10.10.10.10

# Im Heimnetz, falls mDNS/Avahi funktioniert:
ssh tihulu-kit@tihulu.local

# Über Router oder direkte Ethernet-Verbindung:
ssh tihulu-kit@<tatsaechliche-pi-ip>
```

Die letzte Adresse durch die tatsächliche IP des Pi ersetzen. `10.10.10.10` gilt nur für den geplanten Pi-Hotspot. Der Router löst `tihulu.lan` nicht automatisch auf. Bei der Anmeldung das lokal festgelegte **SSH-Kontopasswort** verwenden, nicht das WLAN- oder Web-Passwort. Den SSH-Hostschlüssel vor dem ersten Vertrauen über einen unabhängigen Weg prüfen.

## Aktivierung, Passwortwechsel und Fehler

Die geplanten Menüs `Guide > Netzwerk & SSH` und `Settings > Security > SSH / Remote Access` sollen den tatsächlichen Dienststatus sowie die gültige Adresse anzeigen. Der autorisierte Besitzer kann SSH aktivieren/deaktivieren, Passwörter und öffentliche SSH-Schlüssel verwalten und den Zugriff auf vertrauenswürdige lokale Schnittstellen beschränken. Keine öffentlich bekannte Standardanmeldung und kein SSH-Zugriff über das Internet als Standard.

Nach erfolgreicher Anmeldung ändert `passwd` das eigene SSH-Passwort interaktiv. Das Web-Administratorkonto und das WLAN-Kennwort bleiben unverändert. Bei `Connection refused` Dienst und Firewall prüfen, bei `Permission denied` den wirklich eingerichteten OS-Benutzer und dessen Anmeldedaten prüfen. Geänderte SSH-Hostschlüssel niemals ungeprüft akzeptieren.

Die normale telefonbasierte Tihulu-Oberfläche benötigt kein SSH. Zum nachträglichen Einbau einer AI HAT siehe [Hardware-Upgrades](AI_HARDWARE_UPGRADES.md).

## Offizielle SSH-Standardeinstellungen

Die [Raspberry-Pi-Dokumentation](https://www.raspberrypi.com/documentation/computers/remote-access.html) bestätigt, dass SSH auf einer normalen Raspberry-Pi-OS-Installation **standardmäßig deaktiviert** ist. Die [Raspberry Pi Imager-Einrichtung](https://www.raspberrypi.com/documentation/computers/getting-started.html) bietet **Remote Access → Enable SSH** und wahlweise individuelle Kennwortauthentifizierung oder öffentliche SSH-Schlüssel. Erst eine echte personalisierte Tihulu-Installation kann den Benutzer `tihulu-kit` anlegen und SSH mit Besitzerberechtigung aktivieren.
