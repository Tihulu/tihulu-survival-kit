# AI HAT+ 2 nach der Installation — Erkennung beim Start und Moduswechsel

> **Status (6. November 2026):** Geplante Stage-10-Erweiterung, noch kein fertiger Raspberry-Pi-Bootdetektor.

## Ablauf nach einem Hardware-Upgrade

1. Vor dem Wechsel von PCIe-Hardware den Raspberry Pi **vollständig ausschalten**. Der einzelne externe PCIe-Anschluss des Pi 5 kann bereits vom NVMe-Bootlaufwerk genutzt werden. Falls der Pi nach dem Umbau nicht startet, kann keine Software die neue HAT erkennen; zuerst eine getestete Boot-/Speicherlösung schaffen.
2. Nach Prüfung von Anschluss, Stromversorgung und Kühlung die kompatible AI HAT+ 2 einbauen und den Pi neu starten.
3. Bei **jedem erfolgreichen Start** prüft eine kleine schreibgeschützte Hardwareerkennung Pi/PCIe/Hailo, angeschlossene SSDs, Treiber und verfügbare Laufzeitumgebungen im Vergleich zum zuletzt geprüften Zustand. Eine Erkennung löst **keinen automatischen Download, Treiberwechsel, Modellstart oder Moduswechsel** aus.
4. Bei neuer Hardware erhält der autorisierte Besitzer eine Meldung im Home-/Hardware-Bereich. Eine neue Konfiguration ist ohne Betriebssystem-Neuinstallation über `Settings > Hardware > Detect changes` und `AI Hardware & Model Setup > Recheck` möglich.
5. Die Oberfläche unterscheidet **Hardware erkannt**, **Treiber/Laufzeit installiert**, **kompatibles NPU-Modell installiert**, **real getestet und einsatzbereit** und **aktiven KI-Modus**.
6. Fehlende passende Hailo-Treiber, Laufzeit und Modelle erscheinen im Update Center mit überprüften Quellen, Größen, Lizenzen und eventuell notwendigem Neustart. Installation nur nach ausdrücklicher Zustimmung.
7. Auswahl zwischen **CPU Local**, überprüftem **NPU Local**, separat freigegebenem **privatem LAN-KI-Server** und **Auto/Bevorzugt**. Bereits funktionierende CPU-Konfiguration und Dateien bleiben als mögliche Rückfalllösung erhalten; keine unbemerkte Übertragung privater Daten an externe Server.
8. Bei entferntem/defektem HAT oder fehlender Modell-SSD werden Status und mögliche CPU-Rückkehr transparent angezeigt. Originaldateien, Aufnahmen und andere Dienste dürfen nicht gelöscht werden.

## Geplante Guide-Einbindung und Tests

`Guide > Hardware upgrades > AI HAT+ 2`, `Settings > Hardware > Detect changes` und `Update Center > Hardware dependencies`. Wirkliche Pi5-Starts vor/nach Einbau/Ausbau, Hailo-Modelltests, NVMe-Boot, Speicher, Datenschutz, Stromversorgung und Wiederherstellung sind vor einer Freigabe zwingend. Ein Mock-Test beweist keine echte Hardwarekompatibilität.
