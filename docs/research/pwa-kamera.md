# Reicht die Browser-Kamera der PWA auf dem Pixel?

Research zu Issue #45. Stand: 2026-10-04. Begriffe nach `CONTEXT.md` (**Karte**, **Exemplar**, **Scan**, **Scan-Sitzung**, **Erkennung**, **Prüf-Warteschlange**).

Rahmen: PWA (Vite + React + TS) in Chrome auf einem Google Pixel, HTTPS über Caddy, Frames als JPEG per WebSocket an den Hauptdienst auf dem Pi und weiter zum Erkennungsdienst (ADR 0002, ADR 0003). Ziel: < 500 ms bis zur Entscheidung, Dauer-Scan mit Mehr-Bild-Konsens, Ton und Vibration als Feedback (Scan-UX, Issue #7).

Jede Aussage ist gekennzeichnet:

- **Belegt** – steht in Spec, Chromium-Quelltext oder Hersteller-Doku (Quelle in eckigen Klammern).
- **Schätzung** – eigene Rechnung oder Erfahrungswert ohne Primärquelle.
- **Test am Pixel** – lässt sich nur am echten Gerät klären (siehe Testplan).

Das genaue Pixel-Modell ist hier nicht bekannt. Mehrere Punkte (Nahfokus, Auflösungen, Makro) hängen davon ab.

---

## Kurzfazit

**Die PWA reicht, vorbehaltlich eines kurzen Tests am echten Pixel.** Chrome auf Android greift über Camera2 auf die Kamera zu und reicht fast alle Steuerungen, die ein Karten-Scanner braucht, an die Web-API durch: Rückkamera, Auflösung, Bildrate, Dauer-Autofokus, fester Fokusabstand, Belichtungskorrektur, Messpunkte und Taschenlampe [3][4]. Mit `MediaStreamTrackProcessor` kommt man ohne Umweg über ein `<video>`-Element an jedes einzelne Bild samt Zeitstempel. JPEG-Kodierung geht über `OffscreenCanvas` im Worker [5][7][8]. Bildschirm wachhalten, Vibration und Ton funktionieren nach einem Tipp auf „Scan starten“ [10][11][12].

**Was die PWA nicht kann:**

- Sie kann nicht zwischen den Linsen der Rückkamera wechseln. Chrome zoomt nur per Bildausschnitt, nicht per `CONTROL_ZOOM_RATIO`, und kommt deshalb nie an Ultraweitwinkel oder Makro [3][14].
- Sie kann nicht im Hintergrund oder bei gesperrtem Bildschirm scannen. Das kann aber auch eine native App nicht ohne Foreground-Service, und es wird für den Scan nicht gebraucht [13][15].
- Sie kann keine Bildvorverarbeitung auf dem Gerät mit nativer Geschwindigkeit machen, etwa Passcode-OCR mit ML Kit oder Karten-Zuschnitt.

Keiner dieser Punkte ist für den geplanten Ablauf zwingend. Ob die Hauptkamera die Karte **nah genug scharf** bekommt und ob die **Auflösung für den Passcode** reicht, klärt nur der Test am Pixel.

**Empfehlung:**

1. Mit der PWA bauen.
2. Vorher einen Wegwerf-Prototyp „Kamera-Sonde“ (eine HTML-Seite hinter Caddy) auf dem Pixel laufen lassen (Testplan unten, ca. 1–2 h).
3. Die Scan-Ansicht wird nur nativ (CameraX), wenn eines der Abbruchkriterien greift. Das ist der Rückfall, den ADR 0003 schon vorsieht.

---

## Befunde

### 1. Wie Chrome auf Android die Kamera ansteuert

- Chrome nutzt auf Android die **Camera2-API** (`VideoCaptureCamera2`). Die Vorschau läuft mit `TEMPLATE_PREVIEW` („high frame rate is given priority over highest-quality post-processing“) und im Format `YUV_420_888`. Die Rauschunterdrückung steht auf `FAST`, die Kantenschärfung auf `EDGE_MODE_FAST`. Videostabilisierung wird eingeschaltet, wenn das Gerät sie anbietet. **Belegt** [3]
- Die Bilder laufen über einen `ImageReader` mit `maxImages = 2`. Chrome hält also selbst nur sehr wenige Bilder vor. **Belegt** [3]
- Chrome kennt Pixel-Eigenheiten: Für „Pixel 3“ und „Pixel 3 XL“ wird die Ziel-Bildrate nicht gesetzt (Liste `AE_TARGET_FPS_RANGE_BUGGY_DEVICE_LIST`). Neuere Pixel stehen nicht auf der Liste. **Belegt** [3]

### 2. Auflösung und Bildrate

- Chrome bietet **alle** YUV-Ausgabegrößen an, die die Kamera meldet (`getOutputSizes(YUV_420_888)`). Die maximale Bildrate je Größe kommt aus `getOutputMinFrameDuration`. Im Code steht **keine Obergrenze**. `getUserMedia` wählt die nächstliegende Größe (`findClosestSizeInArray`) und den nächstliegenden Bildraten-Bereich aus `CONTROL_AE_AVAILABLE_TARGET_FPS_RANGES`. **Belegt** [3]
- Ältere Aussagen, Chrome auf Android liefere höchstens 1080p, stammen von 2014–2016 und gelten für den heutigen Code nicht mehr. **Belegt** über den aktuellen Quelltext [3]. Welche Größen das konkrete Pixel tatsächlich meldet (4:3 bis 4000×3000? 4K mit 30 fps?), ist ein **Test am Pixel**.
- `resizeMode: "none"` erzwingt eine native Kameragröße. Mit `"crop-and-scale"` darf der Browser herunterrechnen [2]. Für den Scan ist `"none"` mit einer passenden nativen Größe sinnvoll, damit kein unnötiger Skalierungsschritt anfällt (**Schätzung**).
- **Für den Passcode zählt die Auflösung.** Laut Erkennungs-Research braucht die Karte im Analysebild etwa ≥ 1.070 px Höhe, damit die Ziffern ≥ 16 px hoch sind [16]. Bei 1080p im Hochformat (1920 px Bildhöhe) muss die Karte also mehr als die Hälfte der Bildhöhe füllen. Bei 4:3 mit ~4000×3000 wäre das deutlich entspannter. Für den Embedding-Weg reichen kleine Bilder (der Encoder bekommt 224 px). Den Zuschnitt sollte man aber aus dem großen Bild machen [16].
- `ImageCapture.takePhoto()` liefert die volle Foto-Auflösung, ist aber für Einzelfotos gedacht. `grabFrame()` liefert nur die Auflösung des Videostroms [1][4]. Für einen Dauer-Scan ist `takePhoto()` ungeeignet. Ob ein gelegentliches `takePhoto()` für den Passcode die Vorschau stört und wie lange es dauert, ist ein **Test am Pixel**.

### 3. Fokus, Belichtung, Taschenlampe, Zoom

Die Spec *MediaStream Image Capture* erweitert die Track-Constraints um `focusMode`, `focusDistance` (in Metern), `exposureMode`, `exposureCompensation`, `exposureTime`, `iso`, `whiteBalanceMode`, `colorTemperature`, `pointsOfInterest`, `torch`, `zoom` u. a. Die Modi lauten `none | manual | single-shot | continuous` [1]. Chrome setzt sie auf Android so um (**belegt** [3]):

| Constraint | Camera2-Umsetzung in Chrome | Bedeutung für den Scan |
|---|---|---|
| `focusMode: "continuous"` | `CONTROL_AF_MODE_CONTINUOUS_PICTURE` | Dauer-Autofokus, für Freihand der Normalfall |
| `focusMode: "manual"` + `focusDistance` | `CONTROL_AF_MODE_OFF` + `LENS_FOCUS_DISTANCE = 1/Meter` | Fester Fokus. Passt für die **Halterung** mit festem Abstand und spart das Pumpen des Autofokus. |
| `focusDistance`-Bereich | min aus `LENS_INFO_MINIMUM_FOCUS_DISTANCE`, max aus `LENS_INFO_HYPERFOCAL_DISTANCE`, Schritt 0,01 | `getCapabilities().focusDistance.min` zeigt die **Naheinstellgrenze** der Linse |
| `focusMode: "single-shot"` | wird gemeldet (`AF_MODE_AUTO`/`MACRO`). In der gelesenen Methode `configureCommonCaptureSettings` wird er aber nicht gesetzt. | nicht verlassen; **Test am Pixel** |
| `pointsOfInterest` | `CONTROL_AF/AE/AWB_REGIONS` (Rechteck mit 1/8 der Bildgröße) | Fokus und Belichtung auf die Kartenmitte legen |
| `exposureMode: "manual"` + `exposureTime`/`iso` | `CONTROL_AE_MODE_OFF` + `SENSOR_EXPOSURE_TIME`/`SENSOR_SENSITIVITY` | kurze Belichtung gegen Verwackeln möglich |
| `exposureCompensation` | `CONTROL_AE_EXPOSURE_COMPENSATION` | knapp belichten gegen Glanz auf Foils |
| `torch: true` | `FLASH_MODE_TORCH` (mit AE an) | Licht; kann bei Foils mehr Reflexe machen (**Schätzung**) |
| `zoom` | `SCALER_CROP_REGION`, max `SCALER_AVAILABLE_MAX_DIGITAL_ZOOM` | **nur digitaler Ausschnitt** |

- `getCapabilities()`/`getSettings()` sind erst verlässlich, wenn der Stream läuft [4]. Die Sonde muss sie also nach dem ersten Bild abfragen.
- Auf Android unterstützt Chrome von Schwenken/Neigen/Zoomen nur **Zoom** (PTZ-Doku zu Chrome 87) [9]. Für den Scan ist das ohne Bedeutung.

### 4. Linsenwahl

- Chrome zählt die Kameras über `CameraManager.getCameraIdList()` auf und filtert nicht. Die Labels lauten z. B. „camera 0, facing back“. **Belegt** [3]
- Android empfiehlt den Herstellern, die einzelnen physischen Kameras einer Seite **hinter einer logischen Kamera zu verstecken**. Der Wechsel zwischen Ultraweitwinkel, Weitwinkel und Tele soll über `CONTROL_ZOOM_RATIO` laufen, `SCALER_CROP_REGION` nur für den Ausschnitt [14][15]. Chrome nutzt `CONTROL_ZOOM_RATIO` **nirgends**, sondern nur `SCALER_CROP_REGION` [3].
- **Folge:** Mit `facingMode: "environment"` bekommt die PWA praktisch die **Hauptkamera**. Ultraweitwinkel oder eine Makro-Funktion, die auf einer anderen Linse liegt, ist aus dem Browser nicht erreichbar. Ob das Pixel zusätzliche Rückkameras in `enumerateDevices()` zeigt, ist ein **Test am Pixel**.
- Für Karten auf 10–20 cm Abstand ist die Hauptkamera die richtige Linse, solange ihre Naheinstellgrenze (`focusDistance.min`) klein genug ist. Das ist eine **Schätzung**, den Wert liefert der **Test am Pixel**.

### 5. Bilder effizient herausholen

Es gibt vier Wege, die Bilder abzugreifen:

| Weg | Eigenschaften | Bewertung |
|---|---|---|
| `<video>` + `canvas.drawImage` + `toBlob` | Läuft im Haupt-Thread, mit `requestVideoFrameCallback`. Der Takt ist höchstens die Bildwiederholrate, ausgelassene Bilder erkennt man über `presentedFrames`, dazu gibt es `captureTime` [6]. | Einfach und überall verfügbar. Rückfall, falls die anderen Wege hängen. |
| `ImageCapture.grabFrame()` | `ImageBitmap` in Stream-Auflösung, ein Promise je Bild [1] | Brauchbar, aber ohne Zeitstempel und ohne Rückstau-Steuerung |
| **`MediaStreamTrackProcessor`** (Breakout Box) | `ReadableStream` aus `VideoFrame` mit `timestamp`. Bei `maxBufferSize` voll wird das älteste Bild verworfen, Größe 1 heißt „immer das neueste“ [7]. In Chrome seit 94 auf Desktop, **Android** und WebView [17]. Die Spec sieht ihn nur im Worker vor, Chrome bietet ihn auch auf `window` an [7][18]. Jedes `VideoFrame` muss sofort mit `close()` freigegeben werden [8]. | **Empfohlen.** Er passt genau zum Muster „nimm das neueste Bild, sobald der letzte Upload raus ist“. |
| `ImageCapture.takePhoto()` | volle Foto-Auflösung, Blob [1][4] | nur für Einzelbilder (Passcode-Option), nicht für den Dauer-Scan |

- **JPEG:** WebCodecs hat **keinen** Bild-Encoder, nur `ImageDecoder` [8]. JPEG entsteht über `OffscreenCanvas.convertToBlob({ type: "image/jpeg", quality })`. Das geht auch im Worker [5].
- **Vorgeschlagene Kette** (**Schätzung**, im Test zu messen):
  1. `MediaStreamTrackProcessor` mit `maxBufferSize: 1`.
  2. `createImageBitmap(frame, { Zuschnitt auf Kartenbereich, ggf. resize })`, dann `frame.close()`.
  3. `OffscreenCanvas` und `convertToBlob` als JPEG mit Qualität ~0,8.
  4. Binär über den WebSocket senden.
  5. Höchstens 1–2 Bilder gleichzeitig unterwegs halten.

  Ob der Prozessor im Worker läuft (Track per `postMessage` übertragen) oder im Haupt-Thread, entscheidet der Test. Der Haupt-Thread reicht, solange React dort nicht ruckelt.
- **Latenz auf dem Handy:** Dafür gibt es keine Primärquelle. Die Erkennungs-Research schätzt Zuschnitt plus JPEG auf dem Pixel auf 10–30 ms [16]. Die Upload-Zeit im WLAN liegt bei ~100–300 KB je Bild im Bereich weniger zehn Millisekunden (**Schätzung**). Den Aufschlag durch den Pi deckelt ADR 0002 auf < 50 ms (p95). **Test am Pixel:** p50/p95 von „Bild aufgenommen“ (`VideoFrame.timestamp`) bis „JPEG gesendet“ und bis „Antwort zurück“.
- **Folge für den Konsens:** Drei sichere Bilder in Folge innerhalb von 500 ms verlangen einen Durchsatz von mindestens ~6–8 Erkennungen pro Sekunde. Sonst muss die Pipeline 2 Bilder gleichzeitig unterwegs halten (**Rechnung**). Die Kamera liefert 30 fps. Der Engpass ist die Rundreise, nicht die Kamera.

### 6. Bildschirmsperre und App-Wechsel

- Wird das Dokument unsichtbar, **soll** der Browser den Track stummschalten (`mute`) und erst wieder freigeben (`unmute`), wenn es sichtbar wird. `ended` heißt, die Quelle ist endgültig weg [2].
- Chrome auf Android **pausiert die Kameraaufnahme**, sobald die Seite verborgen wird, und gibt die Kamera dabei frei. Bildschirmaufnahme läuft weiter, Kameraaufnahme nicht. **Belegt** über Chromium-Code-Reviews von 2015/2017 [19][20]. Die alten Reviews sind die einzigen Primärbelege. Das heutige Verhalten (mute/unmute oder neu starten, bleiben Fokus und Torch erhalten?) ist ein **Test am Pixel**.
- Android selbst verbietet Apps im Hintergrund den Kamerazugriff (seit Android 9). Nur ein Foreground-Service darf das [13]. Eine native Scan-Ansicht hätte also dieselbe Grenze.
- Auf Mobilgeräten ist der Wechsel nach `hidden` oft das letzte Ereignis, das die Seite noch sicher sieht [21].
- **Vorschlag für die Erfassung:** `visibilitychange → hidden` behandeln wie „Karte wurde weggenommen“. Mit Kandidaten wird daraus ein Eintrag in die Prüf-Warteschlange, ohne Kandidaten kein Scan. Die Scan-Sitzung bleibt offen. Bei `visible`: Wake Lock neu anfordern, Track prüfen (`readyState`, `muted`), notfalls `getUserMedia` neu, Constraints neu setzen. Das ist eine fachliche Entscheidung für Issue #7 bzw. die Erfassung, hier nur als Vorschlag.

### 7. Wake Lock

- `navigator.wakeLock.request("screen")` gibt es nur im Secure Context, und nur, wenn das Dokument sichtbar und aktiv ist. Beim Verbergen wird der Lock **automatisch freigegeben** und muss bei `visible` neu angefordert werden [10].
- Der Browser **darf** den Lock ablehnen, z. B. bei Energiesparmodus oder niedrigem Akku [10]. Die PWA muss die Ablehnung anzeigen (grauer Hinweis) und darf sich nicht darauf verlassen.
- Für die Halterung über der Ablage ist das der entscheidende Baustein, sonst schaltet sich der Bildschirm nach der System-Zeit ab und die Kamera pausiert (siehe 6). Ob Chrome den Lock bei Energiesparen auf dem Pixel tatsächlich verweigert, ist ein **Test am Pixel**.

### 8. Vibration und Ton

- **Vibration:** `navigator.vibrate(pattern)` verlangt **Sticky Activation**: Der Nutzer muss einmal mit der Seite interagiert haben. Ist die Seite unsichtbar, gibt die Methode `false` zurück und laufende Muster brechen ab. Muster sind auf 10 Einträge und 10 s je Eintrag begrenzt [11]. Kurz, doppelt und lang aus Issue #7 lassen sich also abbilden. Nur Chromium unterstützt die API, für Chrome auf Android passt das.
- **Ton:** Ein `AudioContext`, der vor einer Nutzergeste erzeugt wird, startet `suspended` und braucht `resume()` nach einem Klick [12]. Der Tipp auf „Scan starten“ schaltet also Ton und Vibration für die ganze Scan-Sitzung frei. Die Töne erzeugt man am besten per Oszillator in Web Audio (kein Laden, kein `<audio>`), mit `latencyHint: "interactive"` (**Schätzung**).
- **Test am Pixel:** Vibriert es bei Stumm- oder „Bitte nicht stören“-Modus und mit den System-Einstellungen für Vibration? Wie groß ist die Verzögerung des Tons (`AudioContext.outputLatency`)? Bleibt der `AudioContext` nach Sperre und Rückkehr aktiv?

### 9. Was eine native Scan-Ansicht (CameraX) konkret mehr bringt

| Punkt | PWA (Chrome) | Nativ (CameraX/Camera2) |
|---|---|---|
| Linsenwechsel und Makro | nur Hauptkamera, digitaler Zoom [3] | `setZoomRatio` bzw. `CONTROL_ZOOM_RATIO` schaltet die Linsen der logischen Kamera um, auch < 1× [14][15][22]. Physische Kameras sind direkt ansprechbar [15]. |
| Bildzugriff | `VideoFrame`, dann JPEG über Canvas | `ImageAnalysis` mit `STRATEGY_KEEP_ONLY_LATEST`, YUV oder RGBA direkt, ohne Browser-Prozessgrenzen [23] |
| Vorverarbeitung auf dem Gerät | nur JS/WASM | ML Kit (Passcode-OCR on-device) [16], Karten-Zuschnitt vor dem Upload |
| Fokus/Belichtung | fast alles über Constraints [3] | dazu `startFocusAndMetering`, Camera2Interop für jeden `CaptureRequest`-Schlüssel [22] |
| Ton/Vibration | nach Nutzergeste, nur bei sichtbarer Seite [11][12] | jederzeit und mit System-Haptik |
| Hintergrund | nein [19] | nur mit Foreground-Service [13]. Für den Scan nicht nötig. |
| Kosten | keine neuen | Kotlin als dritte Sprache, APK-Installation von Hand, eigener Release-Pfad, Typen aus dem JSON Schema des Scan-WebSockets zusätzlich nach Kotlin (ADR 0003) |

**So würde sie neben der PWA leben (Skizze):**

1. Eine kleine Android-App mit genau einer Activity, der Scan-Ansicht. Sie spricht denselben Scan-WebSocket des Hauptdienstes wie die PWA (gleiche Nachrichten, gleiche Origin über Caddy).
2. Die PWA startet sie über einen `intent:`-Link mit `S.browser_fallback_url` auf die Web-Scan-Ansicht. Das muss von einer Nutzergeste ausgehen [24].
3. Am Ende der Scan-Sitzung kehrt der Nutzer zur PWA zurück. Sammlung, Listen und Prüf-Warteschlange bleiben in der PWA.

So bleibt die Datenhaltung allein auf dem Pi (ADR 0002), und die native App ist nur ein weiterer Client der Erfassung.

---

## Testplan am echten Pixel („Kamera-Sonde“)

Eine Wegwerf-Seite (Single HTML, kein Build) unter der Caddy-Subdomain. Sie schreibt alle Messwerte als JSON in die Seite und lädt sie auf Knopfdruck hoch. Dazu ein winziger Echo-Endpunkt per WebSocket auf dem Pi, der für die Rundreise jedes JPEG sofort mit Zeitstempel beantwortet. Dauer ca. 1–2 h. Vorher notieren: Pixel-Modell, Android- und Chrome-Version.

| # | Test | Messen | Bestanden, wenn (Vorschlag) |
|---|---|---|---|
| T1 | **Fähigkeiten auslesen** | `enumerateDevices()`-Labels. `getCapabilities()`/`getSettings()` der Rückkamera nach dem ersten Bild: width/height/frameRate max, `focusMode`, `focusDistance` min/max, `exposureMode`, `exposureCompensation`, `torch`, `zoom`, `pointsOfInterest`. `'MediaStreamTrackProcessor' in window`. | `continuous` und `manual` beim Fokus vorhanden, `torch` vorhanden |
| T2 | **Auflösung × Bildrate** | 1920×1080, 3840×2160 und die größte 4:3-Größe jeweils mit `frameRate: 30` und `resizeMode: "none"`. Tatsächliche fps über `VideoFrame.timestamp` | eine Größe mit ≥ 1.070 px Kartenhöhe bei bequemem Abstand **und** ≥ 24 fps |
| T3 | **Nahfokus** | Karte in 8/10/12/15/20 cm, Dauer-AF. Schärfe-Maß (Laplace-Varianz) und Ziffernhöhe des Passcodes in px. Für die Halterung: `manual` mit fester `focusDistance`. | Bei dem Abstand, bei dem die Karte ≥ 1.070 px hoch ist, wird sie scharf. Bei festem Fokus bleibt sie scharf. |
| T4 | **Pipeline-Latenz** | Je Bild: `timestamp` → Bitmap → JPEG (Qualität 0,7/0,85/0,95, ganzes Bild vs. Zuschnitt) → gesendet → Echo zurück. p50/p95, einmal im Haupt-Thread, einmal im Worker. Dazu die JPEG-Größen. | p95 „Aufnahme bis gesendet“ ≤ 60 ms, Rundreise über den Pi ≤ 120 ms (ohne Erkennung) |
| T5 | **Glanz und Belichtung** | Foil- und Holo-Karten mit Torch an/aus, `exposureCompensation` 0/−1/−2, `pointsOfInterest` auf der Kartenmitte | eine Einstellung, bei der Name und Bild nicht überstrahlt sind (Sichtprüfung, Bilder fürs Eval-Set behalten) |
| T6 | **Lebenszyklus** | Bildschirm sperren, App-Wechsel, Benachrichtigungsleiste, Anruf. Ereignisse `mute`/`unmute`/`ended`, Zeit bis zum ersten neuen Bild, bleiben Fokus und Torch erhalten, Wake Lock neu anfordern | nach Rückkehr ≤ 1 s wieder Bilder oder sauberer Neustart per Code, kein Absturz |
| T7 | **Feedback** | `vibrate()` mit den drei Mustern bei normal, stumm und „Bitte nicht stören“. Ton per Oszillator, `outputLatency`, Ton nach Sperre und Rückkehr | Ton und Vibration im Normalmodus zuverlässig, Verzögerung ≤ 100 ms |
| T8 | **Dauerlast** | 15 min Dauer-Scan in der Halterung mit Wake Lock: fps-Verlauf, Akku-%, Erwärmung (Drosselung) | Bildrate fällt nicht unter 20 fps, kein Abbruch |

**Abbruchkriterien → native Scan-Ansicht:**

- T3 scheitert: Die Hauptkamera wird bei der nötigen Nähe nicht scharf, und die Auflösung reicht auch aus größerem Abstand nicht.
- T4: p95 auf dem Handy ist deutlich über 100 ms und lässt sich durch Zuschnitt oder Worker nicht senken.
- T6: Nach Sperre oder App-Wechsel bleibt die Kamera hängen, und auch ein Neustart per Code hilft nicht.

Alle anderen Befunde sind Stellschrauben innerhalb der PWA.

Nebenbei liefert die Sonde echte Clips für das **Eval-Set** (Issue #3): JPEGs in der realen Analyseauflösung, mit Fokus- und Belichtungs-Metadaten.

---

## Offene Punkte

- Das genaue **Pixel-Modell** ist nicht bekannt. Naheinstellgrenze, Auflösungen und mögliche weitere Rückkameras hängen davon ab.
- Für **Chromes heutiges Verhalten** bei Sperre und App-Wechsel gibt es nur Code-Reviews von 2015/2017 als Primärbeleg. Die aktuelle Version prüft T6.
- **Track im Worker:** Ob Chrome auf Android das Übertragen eines `MediaStreamTrack` in einen Worker unterstützt, wurde nicht nachgelesen. Der Haupt-Thread ist der sichere Weg, T4 vergleicht beide.
- Der **Single-Shot-Fokus** ist in Chromes Android-Code nur teilweise sichtbar. Der Scan braucht ihn nicht, daher ist er nicht weiter verfolgt.

---

## Quellen

1. W3C, MediaStream Image Capture (Editor's Draft): https://w3c.github.io/mediacapture-image/
2. W3C, Media Capture and Streams (Editor's Draft), Abschnitte „Life-cycle and Media Flow“, `resizeMode`, `facingMode`: https://w3c.github.io/mediacapture-main/
3. Chromium, `media/capture/video/android/java/src/org/chromium/media/VideoCaptureCamera2.java` (Branch `main`, gelesen 2026-10-04): https://source.chromium.org/chromium/chromium/src/+/main:media/capture/video/android/java/src/org/chromium/media/VideoCaptureCamera2.java
4. Chrome for Developers, „Take photos and control camera settings“ (ImageCapture, Chrome 59): https://developer.chrome.com/blog/imagecapture
5. MDN, `OffscreenCanvas.convertToBlob()`: https://developer.mozilla.org/en-US/docs/Web/API/OffscreenCanvas/convertToBlob
6. MDN, `HTMLVideoElement.requestVideoFrameCallback()`: https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback
7. W3C, MediaStreamTrack Insertable Media Processing using Streams (`MediaStreamTrackProcessor`, `maxBufferSize`): https://w3c.github.io/mediacapture-transform/
8. W3C, WebCodecs (`VideoFrame`, `close()`, `ImageDecoder`): https://w3c.github.io/webcodecs/
9. web.dev, „Control camera pan, tilt, and zoom“ (Chrome 87, Android nur Zoom): https://web.dev/camera-pan-tilt-zoom
10. W3C, Screen Wake Lock API: https://w3c.github.io/screen-wake-lock/
11. W3C, Vibration API: https://w3c.github.io/vibration/
12. Chrome for Developers, „Autoplay policy in Chrome“ (Web Audio, `resume()`): https://developer.chrome.com/blog/autoplay
13. Android Developers, Android 9 Behavior Changes, „Limited access to sensors in background“: https://developer.android.com/about/versions/pie/android-9.0-changes-all
14. Android Open Source Project, „Multi-camera support“ (`CONTROL_ZOOM_RATIO`, Verstecken physischer Kameras): https://source.android.com/docs/core/camera/multi-camera
15. Android Developers, „Multi-camera API“: https://developer.android.com/media/camera/camera2/multi-camera
16. Research zu Issue #3, „Erkennung unter 1 s“ (Branch `research/erkennung`): https://github.com/DoenerbudenAli/yugioh-collection/blob/research/erkennung/docs/research/erkennung.md
17. Chrome Platform Status, „MediaStreamTrack Insertable Streams (a.k.a. Breakout Box)“: https://chromestatus.com/feature/5499415634640896
18. MDN, `MediaStreamTrackProcessor` (Chrome bietet es auch auf `window` an): https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrackProcessor
19. Chromium Code Review 2763743002, „Android: not to pause screen capture when Chrome is put to background“ (2017): https://codereview.chromium.org/2763743002
20. Chromium Code Review 1294953004, Kamera-Start/-Stopp bei `OnWasHidden`/`OnWasShown` auf Android (2015): https://codereview.chromium.org/1294953004
21. Chrome for Developers, „Page Lifecycle API“: https://developer.chrome.com/docs/web-platform/page-lifecycle-api
22. Android Developers, CameraX „Configuration options“ (`CameraControl`, Zoom, Torch, Fokus/Messung): https://developer.android.com/media/camera/camerax/configuration
23. Android Developers, CameraX „Image analysis“: https://developer.android.com/media/camera/camerax/analyze
24. Chrome for Developers, „Android Intents with Chrome“: https://developer.chrome.com/docs/android/intents
