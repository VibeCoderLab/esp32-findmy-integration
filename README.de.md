# ESP32 Find My – experimenteller Tracker für Linux

Version **0.1.1**. Siehe [Änderungen](CHANGELOG.md) und [Release Notes](docs/RELEASE-v0.1.1.md).

Eingabeaufforderungen, Fortschrittsmeldungen und Fehler des Projekts sind unabhängig von der Systemsprache auf Englisch. Externe Werkzeuge können eigene Spracheinstellungen verwenden.

[English](README.md)

Eigene ESP32-Firmware und Linux-Werkzeuge für einen experimentellen Eintrag in
Apples „Wo ist?“. Kein Mac und kein eigener AirTag erforderlich. Die
Firmware sendet BLE-Beacons; Apple-Geräte in der Nähe können verschlüsselte
Standortberichte erzeugen. Der ESP32 hat kein GPS.

**Funktionsumfang:** Native Nähe-Suche, UWB-Präzisionssuche und Tonwiedergabe
werden nicht unterstützt.

Im ursprünglichen Hardwareversuch funktionierten Standortanzeige, Name und
Emoji in Apples App mit der AirTag-Produktklasse. Diese bereinigte Fassung
erzeugt neue Schlüssel und Kennungen pro Installation. Ihre Offline-Tests und
der Firmware-Build lassen sich ohne Apple-Anmeldung prüfen. Ein frischer ZIP-Durchlauf wurde mit dem ursprünglichen Account bestätigt.
Die Einrichtung mit einem anderen Account ist noch separat zu validieren.
Apple kann die verwendeten privaten Schnittstellen jederzeit ändern.

## Voraussetzungen

- Linux, Python 3.12, Git, `curl`, `7z` und [uv](https://docs.astral.sh/uv/).
- Klassischer ESP32 mit BLE, z. B. ESP32-D0WD/ESP32-WROOM; ESP32-S2 hat kein BLE.
  Andere Chipfamilien sind mit dieser Konfiguration nicht getestet.
- USB-Datenkabel, Zugriff auf den seriellen Port und optional ein Linux-BLE-Adapter.
- Eigener Apple-Account mit Zwei-Faktor-Anmeldung und einer wiederherstellbaren
  iCloud-Schlüsselbund-Geräteidentität; der Entsperrcode dieses Geräts muss bekannt sein.
- Eine bestehende BeaconStore-Zone mit wiederherstellbaren Zonenschlüsseln im
  eigenen Apple-Account. Eine Verschlüsselungsvorlage von Zubehör ist im
  Standardmodus nicht erforderlich. Ein leerer oder neuer Account ist noch
  nicht als funktionierend nachgewiesen.

Die Skripte schreiben keine vorhandenen Geräte um. Sie legen genau ein eigenes
Paar neuer Datensätze an. Nur eigene Geräte und Gegenstände damit verwenden.

## Empfohlen: Einrichtung mit einem Befehl

Sind die Voraussetzungen installiert und nur der gewünschte klassische
4-MB-ESP32 angeschlossen, genügt im entpackten Projektordner:

```bash
chmod +x scripts/*.sh
scripts/install.sh --port /dev/ttyUSB0 --name 'ESP32 Tracker' --emoji '📍'
```

Der Installer übernimmt Abhängigkeiten, Boardprüfung, Flash-Sicherung,
Apple-Anmeldung, Schlüsselvorbereitung, iCloud-Registrierung, Build, Upload,
serielle Schlüsselprüfung und Standortabfrage. Passwort und Codes werden
interaktiv im Terminal eingegeben. `--verify-ble` ergänzt einen Empfangstest
über einen Linux-Bluetooth-Adapter.

Der gewählte ESP32 wird überschrieben. Seine Sicherung liegt unter
`private/installer-flash-before.bin`; `installer-board.json` bindet sie an
Hardwarekennung und SHA-256. Beim Fortsetzen werden dieselben Schlüssel und
Eintrags-IDs verwendet. Bei Teilfehlern entstehen keine automatischen Duplikate.
Der Installer löscht lokale Apple-Sitzungstokens bei Erfolg, Fehlern und
behandelbaren Abbrüchen. Beim Fortsetzen meldest du dich erneut an; Schlüssel
und Sicherungen bleiben erhalten. Für die Einzelbefehle gibt es
`scripts/logout.sh`. Das widerruft keine Sitzung auf Apples Servern.
Bei Stromausfall oder nicht abfangbarem Prozessabbruch kann die Bereinigung
ausbleiben; dann `scripts/logout.sh` ausführen.
Die Anzeige in „Wo ist?“ bleibt abschließend zu prüfen;
direkt nach dem Flashen sind 0 Standortberichte möglich.
**Bis zur ersten Standortanzeige in „Wo ist?“ kann es ungefähr eine halbe Stunde
dauern.** Das ist ein beobachteter Richtwert, keine garantierte Obergrenze;
längere Verzögerungen sind möglich. Lass den ESP32 am Strom und in Reichweite
eines teilnehmenden Apple-Geräts.

Standardmäßig werden neue Verschlüsselungshüllen lokal erzeugt. `--fresh-protection`
ist nicht mehr erforderlich und bleibt als kompatible Option erhalten. Die Methode
ist weiterhin experimentell. Neue Verschlüsselungshüllen werden
ohne Zubehör-Vorlagen erstellt, aber mit den Zonenschlüsseln des angemeldeten
Accounts. Eine bestehende BeaconStore-Zone bleibt erforderlich. Lokale Tests
bestehen. Nach Korrektur der Zonenschlüsselauswahl wurde ein vorlagenfreier
Testeintrag mit Standort auf einem Apple-Gerät bestätigt. Anschließend wurden
auch beim vollständigen Durchlauf aus einer frischen ZIP Sichtbarkeit,
Namens-/Emoji-Änderung und Standort bestätigt. Ein leerer Account ist weiterhin
nicht geprüft. Details:
[experimenteller Ansatz](docs/FRESH-PROTECTION.md).

Zubehör wie AirTags oder AirPods wird nicht als Verschlüsselungsvorlage benötigt.
Der ältere Vorlagenmodus ist nur über `--template-protection` verfügbar und
benötigt entschlüsselbare bestehende Datensätze. Zum Fortsetzen einer alten
Vorlageninstallation muss dieser Modus ausdrücklich gewählt werden; bestehende
Registrierungen werden nicht automatisch ersetzt.

Die folgenden Abschnitte erklären dieselben Schritte als Einzelbefehle.

## 1. Abhängigkeiten einrichten

Dieses Verzeichnis in einen eigenen Projektordner entpacken und darin arbeiten:

```bash
scripts/setup.sh
```

Das Skript lädt die festgelegte Version von
[os-findmy-e](https://github.com/sacca97/os-findmy-e), installiert Python-
Abhängigkeiten in `.venv/` und bezieht CoreADI über den Upstream-Downloader aus
Apples iTunes-Download. Der Downloader prüft dessen SHA-256. Apple-Bibliotheken
werden nicht mit diesem Projekt ausgeliefert. Die Patches unter `patches/`
passen Login-Diagnose, Maschinenzustand und HTTP-Fehlerbehandlung an.
Python-3.12-Abhängigkeiten und Build-Helfer werden aus Hash-Lockdateien installiert.
FindMy wird aus einem separat hashgeprüften Commit-Archiv mit geprüfter
Paketkorrektur gebaut; siehe [Herkunft](THIRD_PARTY.md).

Für Login sowie CloudKit/Schlüsselbund/Standortdienste gibt es lokale Sperren.
Ohne nutzbare Serverangabe beträgt die Ersatzwartezeit fünf Minuten. Eine
Serverwartezeit hat Vorrang; es gibt keine automatische Wiederholung oder
Neuanmeldung. Die Sperrinformationen liegen unter `$XDG_STATE_HOME/esp32-findmy`
(gewöhnlich `~/.local/state/esp32-findmy`) und gelten auch über Projektkopien hinweg.
Apples tatsächliche Sperrdauer kann davon abweichen.

Standardmäßig liegen **Zugangsdaten, Trackerzustand und Journale unter `private/`**. Optional vor allen
Befehlen `ESP32_FINDMY_STATE` auf denselben anderen privaten Ordner setzen.
Die `.gitignore` schützt diesen beliebigen externen Ordner nicht; niemals seine
Inhalte in ein Repository kopieren.

## 2. Apple-Anmeldung im lokalen Terminal

```bash
scripts/login.sh
```

Beim ersten Aufruf richtet der Login-Helfer die emulierte Maschine automatisch
ein, bevor er nach Apple-Zugangsdaten fragt. Spätere Aufrufe verwenden dieselbe
Identität. Bei unvollständigen Bestandsdaten wird keine Ersatzidentität erzeugt.

Apple-Account, Passwort und einen frischen Bestätigungscode ausschließlich im
lokalen Terminal eingeben. Der Helfer fordert standardmäßig einen SMS-Code für
die erste hinterlegte Nummer an. Passwort und Geräte-Sperrcode werden nicht
gespeichert; **Sitzungstokens und emulierte Maschinenidentität werden gespeichert**.
Sie erlauben weitere Account-Zugriffe und sind Zugangsdaten.

Die emulierte Identität kann in Apples Account-Geräteliste auftauchen. Sie wird
für spätere Zugriffe wiederverwendet und nicht pro Aufruf neu erzeugt.

## 3. Eigenen Eintrag lokal vorbereiten

```bash
scripts/register.sh prepare --name 'ESP32 Tracker' --emoji '📍'
```

Das Apple-Passwort wird erneut nur im Arbeitsspeicher für einen frischen
Recovery-Token benötigt. Danach das passende eigene Gerät auswählen und dessen
**Bildschirmsperrcode** eingeben – keinen SMS-Code, keine SIM-PIN. Es erfolgt
genau ein Versuch, kein automatisches Durchprobieren. Bereits vor dem Aufruf wird
eine Sperre geschrieben. Bei Fehlern oder Abbrüchen bleibt
`private/recovery-blocked.json` als Sperre bestehen; siehe [Fehlerbehebung](docs/TROUBLESHOOTING.md).

Der Schlüsselbund wird über Recovery gelesen, ohne ein neues Mitglied in den
Schlüsselbund-Vertrauenskreis aufzunehmen. Bestehende Zubehörschlüssel werden
nicht kopiert. Für das neue Gerät entstehen eigene P-224-Schlüssel, Rollsecrets,
UUIDs, Hardwarekennung und Serienkennung. Dieser Schritt schreibt **noch keine
neuen CloudKit-Einträge**. Wiederholtes `prepare` ersetzt keine vorhandenen Schlüssel.

Das Produktprofil verwendet die öffentlich dokumentierten Testexport-Werte
`vendorId=76`, `productId=21760`, `roleId=999`, Kennungspräfix `2001`.
Apple kann den Eintrag deshalb als **AirTag/Apple** darstellen; ein freier
Herstellername ist damit nicht registriert. Das Modell-Textfeld ist `ESP32`,
die Versionsangabe `1.0`. Diese Textfelder ändern nicht die ESP32-Hardware.
Der hinterlegte Batteriestand ist ein fester Platzhalter, kein gemessener Wert.
Siehe [Technik und Nachweise](docs/DESIGN.md).

## 4. Die zwei vorbereiteten Einträge anlegen

```bash
scripts/register.sh apply
scripts/register.sh status
```

`apply` erstellt ausschließlich die zwei protokollierten neuen Test-IDs und
liest sie danach erneut. Bestehende Einträge werden nicht geschrieben. Bei einem
fehlgeschlagenen Schreibversuch wird die Entfernung der eigenen Teilanlage
versucht. Bei HTTP 401/429 erfolgt kein weiterer automatischer Cloud-Aufruf.
`cleanup_pending` kennzeichnet unbestätigte Aufräumarbeiten: Journal behalten,
Sitzungs-/Dienstproblem klären und gezielt `scripts/register.sh remove` starten.
Unvollständige Cloud-Listen werden als Fehler behandelt und bestätigen weder
Anlage noch Entfernung.

Jetzt „Wo ist?“ auf iPhone/iPad neu öffnen und den neuen Eintrag prüfen. Name
und Emoji sollten beim AirTag-Profil bearbeitbar sein; erst die Prüfung in
Apples App bestätigt das. Ohne sendenden ESP32 ist noch kein Standort zu erwarten.

## 5. Flash sichern, Firmware bauen und aufspielen

Zuerst den richtigen Port ermitteln:

```bash
ls -l /dev/serial/by-id/
```

Falls nötig den eigenen Benutzer der seriellen Zugriffsgruppe der Distribution
hinzufügen und die Sitzung neu starten. Bei vielen Distributionen heißt diese
Gruppe `dialout`. Port und Flashgröße vor dem Flashen prüfen:

```bash
.venv/bin/python -m esptool --port /dev/ttyUSB0 flash-id
umask 077
mkdir -p private
chmod 700 private
.venv/bin/python -m esptool --port /dev/ttyUSB0 --baud 460800 read-flash 0 0x400000 private/flash-before.bin
```

`0x400000` ist für das getestete **4-MB-Board**. Bei anderen Flashgrößen den Wert
anpassen. Die Sicherung darf nicht veröffentlicht werden.

```bash
scripts/build.sh
scripts/build.sh --target upload --upload-port /dev/ttyUSB0
```

Der Build erzeugt `firmware/include/device_secrets.h` aus den eigenen Schlüsseln.
**Dieser Header und die gebauten BIN/ELF-Dateien enthalten private
Ortungsschlüssel und gehören niemals auf GitHub.** Das Upload überschreibt
Bootloader, Partitionstabelle und Firmware des ausgewählten ESP32.

Nach dem Einschalten läuft der Sender automatisch. Er sendet etwa jede Sekunde
und wechselt den Primärschlüssel alle 15 Minuten. Index und Seed werden im NVS
gespeichert. Stromausfälle pausieren die Rotation; nach Neustart geht es beim
gespeicherten Stand weiter. Der PC muss für das Senden nicht laufen.

## 6. Prüfen und Standorte lesen

Mit Linux-BLE-Adapter und freiem seriellen Port. Nach dem Ein-Befehl-Installer
vor einer Standortabfrage erneut `scripts/login.sh` ausführen, da seine
automatische Abmeldung die Kontositzung entfernt hat. Die serielle/BLE-Prüfung
selbst benötigt keine Apple-Anmeldung:

```bash
.venv/bin/python host/verify.py --port /dev/ttyUSB0
scripts/fetch.sh
# Nur bei Bedarf: genaue Koordinaten ausgeben
scripts/fetch.sh --show-location
```

`verify.py` startet den ESP32 neu, vergleicht aktuelle/nächste Schlüsselableitung
mit FindMy.py und prüft die exakten BLE-Nutzdaten. Der Test des nächsten
Schlüssels beobachtet noch keinen vollständigen zeitgesteuerten 15-Minuten-Wechsel.
BLE-Empfang beweist auch keinen Upload durch ein Apple-Gerät.

Standorte entstehen erst durch meldende Apple-Geräte in Bluetooth-Reichweite.
Es gibt keinen garantierten Meldeabstand. Abfragen lösen keine Meldung aus und
es kann dauern, bis Apples App bereits vorhandene Berichte anzeigt.
UWB-Nahsuche und Ton abspielen sind in dieser Firmware nicht implementiert.

Für Akkubetrieb siehe die [Stromverbrauchsanalyse](docs/POWER.md). Eine gemessene
Akkulaufzeit oder ein geprüftes Stromsparprofil gibt es noch nicht. Die
[Quellcode-/Exportprüfung](docs/RELEASE-REVIEW.md) dokumentiert Datenschutzprüfung
und offene Arbeiten.

## Entfernung und Wiederherstellung

Nach automatischer Abmeldung zuerst wieder anmelden:

```bash
scripts/login.sh
scripts/register.sh remove
scripts/logout.sh
```

Entfernt nur das eigene protokollierte Paar, auch nach einer Namens-/Emoji-
Änderung in der App. Unerwartete Schlüssel- oder Zuordnungsänderungen werden
verweigert. Originalgeräte werden nicht entfernt. Die aktive Sitzung muss gültig
sein. Erst nach bestätigter Entfernung die lokale private Registrierung löschen,
falls sie nicht mehr gebraucht wird; ohne Journal geht die Zuordnung verloren.

Die Sicherung des Ein-Befehl-Installers lässt sich auf dasselbe Board
zurückschreiben (Port entsprechend anpassen):

```bash
.venv/bin/python -m esptool --port /dev/ttyUSB0 --baud 460800 write-flash 0 private/installer-flash-before.bin
```

Wer die manuelle Sicherung aus Abschnitt 5 verwendet, nimmt stattdessen
`private/flash-before.bin`. Wiederherstellen überschreibt die Board-Firmware.
Nach manuellen Standortabfragen mit `scripts/logout.sh` lokal abmelden.

## Tests und GitHub-Export

```bash
.venv/bin/python -m unittest discover -s tests -v
python3 scripts/export.py --check
python3 scripts/export.py
```

Der Export unter `dist/esp32-findmy-public.zip` enthält nur freigegebene
Quelldateien. `private/`, `.deps/`, `.venv/`, `.pio/`, Logs, Flash-Abbilder und
generierte Schlüsselheader werden unabhängig von `.gitignore` ausgeschlossen.
Es gibt keine universellen vorgegebenen Ortungsschlüssel.

Für GitHub das **bereinigte ZIP** entpacken und dessen Inhalt verwenden. Nicht
den Ordner einer bestehenden Installation hochladen. Vor einem eigenen Commit
zusätzlich `git diff --cached` prüfen. Die Exportprüfung findet typische
Geheimnisse, ist aber kein mathematischer Beweis für beliebige spätere Änderungen.

Eigener Code: MIT; Abhängigkeiten und deren Lizenzen: [THIRD_PARTY.md](THIRD_PARTY.md).

Vor dem Praxistest [SECURITY.md](SECURITY.md) und den
[Funktionsprüfplan](docs/FUNCTIONAL-TEST.md) lesen. Recovery hält zeitweise auch
Geräteidentität und Schlüssel weiterer Schlüsselbundbereiche im Prozess; die
Zugangsdaten sind nicht serverseitig auf zwei Tracker-Einträge beschränkt.
