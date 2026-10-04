# Encoder und Inferenz-Runtime für die Erkennung auf der RTX 5080

Research zu Issue #44. Stand: 2026-10-04. Begriffe nach `CONTEXT.md`: **Karte** ist die Spielidentität, **Katalog** die Menge aller Karten, **Exemplar** das physische Stück, **Proxy** ein Exemplar, das kein Original ist. Vorarbeit: `docs/research/erkennung.md` (Issue #3, Branch `research/erkennung`), ADR 0002 (Systemtopologie), ADR 0003 (Stack-Wahl).

Kennzeichnung: **Belegt** heißt, die Aussage steht in der verlinkten Primärquelle. **Schätzung** heißt, es ist eine eigene Rechnung oder Einschätzung ohne Messung. **Spike** heißt, nur eine Messung auf dem Heimrechner kann es klären. Mehrere Yu-Gi-Oh-Zahlen stammen aus einem einzigen jungen Projekt ([yugioh-ar](https://github.com/Adrian-Sandwich/yugioh-ar)). Es misst ausführlich, ist aber nicht unabhängig reproduziert.

## Kurzfazit und Empfehlung

1. **Encoder: DRAW2-ViT als Startpunkt, DINOv2 als lizenzfreie Vergleichslinie.** DRAW2 ist auf Yu-Gi-Oh trainiert und trennt fremde Karten deutlich besser als DINOv2 (Recall bei 0 Falsch-Akzeptanzen 97,1 % gegen 75,6 %, **belegt** [1]). Die Lizenz AGPL-3.0 passt zum Repo unter AGPL-3.0-or-later. Genutzt wird nur die 768-dimensionale Repräsentation für kNN, nicht der Klassifikator. Neue Karten kommen dann über Referenzbilder in den Index, ohne Neutraining. **DINOv3 meiden** (eigene Lizenz mit Zusatzbeschränkungen, Gewichte nur auf Antrag).
2. **Feintuning: zunächst keins.** Erst wenn der Spike Falsch-Akzeptanzen bei deutschen Karten, Foils oder Proxies zeigt, wird DRAW2 (oder DINOv2) per Metric Learning nachtrainiert. Werkzeug dafür: PyTorch mit `pytorch-metric-learning` (MIT), SupCon- oder ArcFace-Loss mit harten Negativen.
3. **Runtime: PyTorch (CUDA-13-Wheels) in Docker als erster Wurf, ONNX Runtime CUDA EP als Alternative hinter dem GPU-Adapter, kein TensorRT.** Das Encoder-Budget ist nicht der Engpass. yugioh-ar braucht 15 ms für 9 Karten auf einer RTX 4070 (**belegt** [1]), für eine Karte auf der RTX 5080 sind es wenige Millisekunden (**Schätzung**). Damit zählen Build- und Pflegeaufwand mehr als die letzte Millisekunde. PyTorch braucht es für Eval, Indexaufbau und ein mögliches Feintuning ohnehin. TensorRT bringt hier keinen spürbaren Gewinn, ist für WSL nicht als Plattform gelistet und erzeugt nicht portable Engines.
4. **Netz: Docker Desktop mit Standard-NAT, kein mirrored Mode.** Mit Docker Desktop lauscht dessen Backend selbst auf dem Windows-Port und reicht Verbindungen über einen Shared-Memory-Kanal in die VM (**belegt** [16]). Der WSL-Netzwerkmodus spielt für veröffentlichte Container-Ports damit kaum eine Rolle. Der Aufschlag dürfte im niedrigen einstelligen Millisekundenbereich liegen, weit unter 50 ms p95 (**Schätzung**). Messen muss das der Spike.
5. **kNN: Brute-Force, kein FAISS.** ~15k–30k Vektoren × 768 in fp16 sind 23–45 MB. Eine Abfrage ist ein Matrix-Vektor-Produkt, auf der GPU im Mikrosekunden- bis niedrigen Millisekundenbereich (**Schätzung**). FAISS selbst nennt den Flat-Index (= Brute-Force) als einzigen exakten Index (**belegt** [20]). Die GPU-Pakete von FAISS gibt es offiziell nur über Conda, das passt schlecht zu uv.

## 1. Encoder

### Kandidaten im Überblick

| Encoder | Lizenz Code / Gewichte | Gegen AGPL-3.0-or-later | Embedding | Parameter | Yu-Gi-Oh-Beleg |
|---|---|---|---|---|---|
| **DRAW2-ViT** (`HichTala/draw2`) | AGPL-3.0 / AGPL-3.0 [2][3] | Kompatibel (gleiche Lizenzfamilie, „or-later“ schließt v3 ein; **Einschätzung, keine Rechtsberatung**) | 768 (ViT-B/16, Basis `google/vit-base-patch16-224-in21k`) [2][4] | 96,4 M [2] | Bester verfügbarer: 99,3 % Top-1 auf 4.000 Händler-Scans gegen 14.278 Karten, 0 Falsch-Akzeptanzen bei 96,2 % Auto-Akzeptanz [1][5] |
| **DINOv2** ViT-S/14, ViT-B/14 | Apache-2.0 / Apache-2.0 [6] | Kompatibel, Apache-2.0 ist mit GPLv3 vereinbar [7] | 384 (S), 768 (B) [6] | 21 M (S), 86 M (B) [6] | Ordnet gut, trennt schlecht: Recall bei 0 Falsch-Akzeptanzen 75,6 % (S) bzw. 71,1 % (B); 91–96 % der Negative über Ähnlichkeit 0,5 [1] |
| **DINOv3** | „DINOv3 License“ (eigene Lizenz) [8][9] | **Problematisch**: Nutzungsverbote (u. a. Militär, Exportkontrolle), Kündigung bei Klage gegen Meta, Weitergabe nur mit Lizenztext [9]. AGPL verbietet zusätzliche Beschränkungen gegenüber Empfängern. Für ein öffentliches AGPL-Repo daher nicht sauber (**Einschätzung**) | k. A. | 21 M (S/16) bis 6,7 B [8] | keiner |
| CLIP/SigLIP-Familie | meist MIT/Apache-2.0 (nicht einzeln geprüft) | – | – | – | keiner; DINOv2 schlägt OpenCLIP beim Wiederfinden einzelner Objekte deutlich (Oxford-M mAP 72,9 gegen 50,7) [10] |

**Belegt aus der Vorarbeit:** DRAW2 ist ein Klassifikator für „13k+“ Karten, trainiert auf dem YGOProDeck-Datensatz [2][3]. Neue Karten fehlen bis zum Neutraining. yugioh-ar umgeht das, indem es die Repräsentation als Embedding für kNN nutzt (768 Dimensionen, ohne die Gewichte zu trainieren) [4]. Neue Karten kommen dann über ein Referenzbild in den Index.

**Was im Paket steckt (belegt [11]):** `model.safetensors` (386 MB), ein `onnx/`-Ordner (für die Browser-Demo), der YOLO-Detektor `ygo_yolo.pt` (20 MB) und `cardnames.json`. Ob das ONNX-Modell die Embeddings oder nur die Klassen-Logits ausgibt, ist **offen**. yugioh-ar fährt Encoder-Varianten in int8, fp32 und fp16 über ONNX Runtime [1]. Den YOLO-Detektor brauchen wir für eine einzelne Karte in der Hand vermutlich nicht (Vorarbeit, Abschnitt 4). Er wäre ebenfalls AGPL-3.0 (Ultralytics [12]).

**Lizenz-Hinweise:**
- AGPL-3.0 von DRAW2 und AGPL-3.0-or-later des Repos vertragen sich, die Kombination steht dann faktisch unter AGPL-3.0. ADR 0003 hat die Lizenz genau dafür gewählt.
- Die DRAW2-Gewichte sind auf YGOProDeck-Bildern trainiert, die Bildrechte liegen bei Konami. Gewichte und Bilder gehören daher nicht ins Repo, sondern in den Zwischenspeicher des Erkennungsdienstes (wie in ADR 0002 für Bilder schon geregelt).
- DINOv2 (Apache-2.0) bleibt die saubere Rückfalloption, falls DRAW2 später doch nicht nutzbar ist.

### Robustheit nach Fall

| Fall | DRAW2-Embedding | DINOv2 | Quelle / Status |
|---|---|---|---|
| Foils | Schwachstelle Starlight: 10/16 akzeptiert; Ghost 6/6, Prismatic Secret 9/9, Secret 29/32 bei Regel Ähnlichkeit ≥ 0,50 und Abstand ≥ 0,25. Fehler fallen unter die Schwelle, gehen also in die Prüf-Warteschlange | nicht gemessen | **belegt** [5] (Händler-Scans) |
| Altkarten | keine Zahlen | keine Zahlen | **Spike** |
| Deutsche Karten | keine Zahlen; Referenzen sind englische Replicas. Artwork-Ausschnitt blendet den Text aus, senkt aber die Ähnlichkeit (ein Foil fiel von 0,63 auf 0,40) | keine Zahlen | Vorarbeit [4]; **Spike** |
| Proxies aus YGOProDeck-Bildern | vermutlich am leichtesten, weil fast identisch mit der Referenz | dto. | **Schätzung** |
| Proxies mit eigenem Artwork | scheitert konstruktionsbedingt | dto. | **Schätzung**; landet in der Prüf-Warteschlange |
| Echte Handyfotos | 16/16 Top-1, 15 akzeptiert, 0 falsch (sehr kleine Stichprobe) | – | **belegt** [1] |

### Feintuning

- **DRAW2: zunächst nicht nötig.** Es ist schon auf Yu-Gi-Oh trainiert und wird ohne Gewichtsänderung als Embedding genutzt [4]. Neue Karten brauchen nur ein Referenzbild.
- **DINOv2: ohne Feintuning nicht tragfähig**, weil sich keine Schwelle mit 0 Falsch-Akzeptanzen bei brauchbarem Recall setzen lässt [1].
- **Wann doch:** wenn der Spike Falsch-Akzeptanzen oder eine niedrige Auto-Akzeptanz bei deutschen Karten, Foils oder Altkarten zeigt. yugioh-ar hat das selbst noch nicht gemacht. Es plant „supervised contrastive“ oder Triplet-Loss mit harten Negativen, getrennt nach Finish-Gruppen [4].
- **Womit (Vorschlag):** PyTorch + `pytorch-metric-learning` (MIT, enthält `SupConLoss`, `ArcFaceLoss`, `TripletMarginLoss` und Miner für harte Negative [13]). Daten: YGOProDeck-Referenzbilder mit Augmentierung (Perspektive, Reflexe, Farbstich, Unschärfe, Hülle), ergänzt um eigene Fotos. Diese müssen streng vom Eval-Split getrennt bleiben. Ein feingetuntes DRAW2 ist ein AGPL-Derivat, das ist für uns unkritisch.

## 2. Inferenz-Runtime

### Blackwell (sm_120) und CUDA

- CUDA 12.8 bringt als erste Version Compiler-Unterstützung für SM_120 (**belegt** [14]). Ältere Builds haben keine Kernel für die RTX 5080, typischer Fehler ist „no kernel image is available“.
- In WSL2 kommt der Treiber **nur aus Windows**. In WSL darf kein Linux-Treiber installiert werden (**belegt** [15]). Die CUDA-Version im Container muss also zum Windows-Treiber passen: CUDA 13.x braucht Treiber ≥ 580 (**belegt** [17]).
- Docker Desktop unterstützt GPU-Passthrough (`--gpus`) nur mit WSL2-Backend und braucht einen aktuellen NVIDIA-Treiber mit WSL2-Paravirtualisierung (**belegt** [18]). Einschränkungen von CUDA unter WSL2: begrenzter Pinned Memory, kein volles Unified Memory, `nvidia-smi` unvollständig (**belegt** [15]). Für Inferenz eines ViT-B ist davon nichts kritisch (**Schätzung**).

### Vergleich

| | PyTorch | ONNX Runtime (CUDA EP) | TensorRT (nativ oder als ORT-EP) |
|---|---|---|---|
| **Blackwell / CUDA** | Blackwell ab 2.7 mit cu128-Wheels [19]. Aktuell 2.14 (2026-09-02) mit CUDA 12.6, 13.0, 13.2; 2.15 folgt am 2026-10-28 [21]. cu126 hat kein sm_120, also **cu130 oder cu132** nehmen | Ab 1.27 sind die PyPI-GPU-Pakete mit CUDA 13.0 gebaut, 1.21–1.26 mit CUDA 12.8; braucht cuDNN 9 [22]. **1.23.0/1.23.1 liefen nicht auf Blackwell** (Build mit `90a-virtual`), behoben in 1.23.2 [23] | TensorRT 11.3 unterstützt ab SM 7.5, Compute Capability 12.0 ist gelistet. **WSL ist keine gelistete Plattform** [24] |
| **Latenz pro Frame** (eine Karte, 224 px, fp16) | wenige ms (**Schätzung**) | wenige ms; yugioh-ar: 9 Karten in 15 ms auf RTX 4070 [1] | evtl. etwas weniger (**Schätzung**), für das Budget irrelevant |
| **Build-Aufwand** | Wheels bringen CUDA-Libs als pip-Pakete mit, Basis-Image kann schlank sein. Image ist groß (mehrere GB, **Schätzung**) | Modell muss mit Embedding-Ausgang nach ONNX exportiert werden (DRAW2-ONNX-Ausgabe **offen**). CUDA/cuDNN müssen im Image passen | Engine-Bau dauert Minuten (ORT-Beispiel 384 s ohne Cache, 9 s mit Engine-Cache [25]). Engines sind nicht zwischen GPU-Architekturen und Plattformen portabel [24] |
| **Pflege** | Ein Stack für Eval, Indexaufbau, Feintuning und Inferenz. Versionswechsel = Wheel-Tag | Zweiter Stack neben PyTorch (Export + Runtime). Regressionen wie 1.23 zeigen: Version pinnen, Smoke-Test auf sm_120 | Neu bauen bei jedem TRT-/Treiber-/Modellwechsel. TensorRT-RTX-EP gibt es bisher nur als Build aus dem Quellcode [26] |

### Empfehlung Runtime

- **Spike und erster Erkennungsdienst mit PyTorch** (cu130 oder cu132, fp16, `torch.inference_mode`). Begründung: Die Latenz ist bei jeder Runtime weit unter dem Budget von 500 ms aus ADR 0002, PyTorch wird für Eval, Indexaufbau und Feintuning ohnehin gebraucht, und DRAW2 sowie DINOv2 laden direkt (Hugging Face `transformers` bzw. `torch.hub` [6]).
- **ONNX Runtime als Alternative im GPU-Adapter**, wenn der Spike Kaltstart, Image-Größe oder Speicher als Problem zeigt. Version pinnen und im CI-Image prüfen, dass sm_120 läuft.
- **TensorRT nicht einsetzen.** Der Gewinn liegt im Bereich weniger Millisekunden, dafür kommen Engine-Bau, fehlende Portabilität und eine nicht gelistete Plattform (WSL) dazu.
- Im Image die CUDA-Version fest pinnen (ADR 0003 verlangt ≥ 12.8). Bei CUDA 13.x muss der Windows-Treiber ≥ 580 sein.

## 3. WSL2-Netzwerk und Latenzgrenze

**Der Weg:** Pi → LAN → Windows-Port des Heimrechners → Docker-Desktop-Backend → Shared-Memory-Kanal → Linux-VM → Container.

- **Belegt:** Bei veröffentlichten Ports lauscht das Backend von Docker Desktop auf dem Host-Port und leitet die Verbindung über einen Shared-Memory-Kanal in die Linux-VM. Standardmäßig bindet `-p` auf `0.0.0.0`, also auch für das LAN erreichbar [16].
- **Belegt:** Im WSL-NAT-Modus ist eine Anwendung *in einer WSL-Distribution* nicht direkt aus dem LAN erreichbar. Dafür braucht es `netsh interface portproxy` [27]. Der mirrored Mode (ab Windows 11 22H2) erlaubt direkten LAN-Zugriff, braucht aber eine Freigabe in der Hyper-V-Firewall [27][28].
- **Daraus folgt (Einschätzung):** NAT oder mirrored betrifft vor allem Server, die direkt in einer WSL-Distribution laufen. Für Container unter Docker Desktop übernimmt Docker Desktop das Port-Forwarding selbst. Im Docker-Forum heißt es, Docker Desktop nutze den mirrored Mode nicht; wer ihn will, müsse Docker Engine direkt in einer WSL-Distribution installieren [29] (Sekundärquelle, Antwort eines erfahrenen Forenmitglieds). Bei WSL 2.0.6 gab es mit mirrored sogar Ausfälle beim Zugriff auf Container-Ports [30].
- **Empfehlung:** Standard-NAT lassen, Port über Docker Desktop veröffentlichen, Windows-Firewall-Regel nur für die IP des Pi (wie in ADR 0002). Kein `netsh portproxy`, kein mirrored Mode.

**Aufschlag gegen die Grenze ≤ 50 ms p95:**
- Eine primäre Messung des Aufschlags durch Docker Desktop oder WSL2 gegenüber nativem Linux wurde **nicht gefunden**. Die Treffer in den WSL-Issues betreffen Durchsatz und DNS, nicht Latenz im LAN [31].
- **Schätzung:** Über die dauerhafte WebSocket-Verbindung aus ADR 0003 fällt kein Verbindungsaufbau pro Frame an. Pro Nachricht kommen eine Kopie im Userspace-Proxy und ein VM-Übergang dazu, also unter 1 ms bis wenige ms. Das ist eine Größenordnung unter der Grenze. Zum Vergleich: Der Pi selbst kostet laut ADR 0002 ~10 ms über eine offene Verbindung durch Caddy.
- **Risiken (Schätzung):** Energiesparen von Netzwerkkarte oder WLAN am Heimrechner, Firewall-Inspektion, Nagle-Verzögerung bei kleinen Antworten (TCP_NODELAY prüfen) und CPU-Konkurrenz durch Spiele auf dem Heimrechner.
- **Nur der Spike kann das klären.** Ein Vergleich mit nativem Linux ist auf dem Heimrechner ohne Dual-Boot nicht möglich. Als Basislinie dient derselbe Echo-Dienst direkt unter Windows.

## 4. kNN-Index

- **Größe (belegt aus Vorarbeit):** 14.597 Karten und 14.769 Bilder inkl. Alt-Arts im YGOProDeck-Katalog; yugioh-ar nutzt 14.782 Referenzen für 14.278 Identitäten [1].
- **Speicher (Rechnung):** 14.800 × 768 × 2 Byte (fp16) ≈ 23 MB. Mit zusätzlichem Artwork-Index ≈ 45 MB. yugioh-ar rechnet für 768 Dimensionen in fp32 mit ≈ 43 MB [4].
- **Rechenzeit (Schätzung):** Eine Abfrage sind ~11 Mio. Multiply-Adds, auf der GPU Mikrosekunden bis unter 1 ms, auf der CPU mit NumPy wenige ms.
- **Belegt:** FAISS selbst sagt, nur `IndexFlatL2`/`IndexFlatIP` liefern exakte Ergebnisse, und bei wenigen Abfragen ist direkte Berechnung am effizientesten [20]. yugioh-ar plant genau das: „búsqueda exacta matricial o IndexFlatIP“ [4].
- **FAISS-GPU passt schlecht zum Stack:** Offiziell nur über Conda, GPU-Pakete mit CUDA 11.4/12.1 bzw. cuVS mit CUDA 13.2, nur Linux x86-64 [32]. Mit uv (ADR 0003) wäre das ein Sonderweg.
- **Empfehlung:** L2-normalisierte Embeddings als ein Tensor auf der GPU, Ähnlichkeit per Matrixprodukt, `topk` über die Referenzen und Zusammenfassen auf Karten (mehrere Alt-Arts je Karte). Den Index mit Katalogstand speichern, wie es der Health-Endpunkt aus ADR 0002 verlangt. Indexaufbau für den vollen Katalog: 3,2 min fp16 auf RTX 4070 bei yugioh-ar [1].

## 5. Was der Erkennungs-Spike messen muss

1. **Encoder-Güte auf dem Eval-Set** (aus der Vorarbeit): DRAW2 ganze Karte vs. Artwork-Ausschnitt vs. DINOv2 ViT-S/B. Messgrößen: Falsch-Akzeptanzrate und Auto-Akzeptanz bei kalibrierter Schwelle (Ähnlichkeit + Abstand), getrennt nach DE/EN, Foil-Art, Alter, Proxy-Herkunft, Alt-Art. Davon hängt ab, ob Feintuning nötig ist.
2. **Blackwell-Smoke-Test im Container:** `torch.cuda.get_arch_list()` enthält `sm_120`, kein JIT-Fallback, Treiberversion ≥ 580 bei CUDA 13.x. Dasselbe für ONNX Runtime, falls getestet.
3. **Encoder-Latenz** p50/p95 pro Frame (eine Karte, fp16) in Docker unter WSL2. PyTorch eager, optional `torch.compile`, optional ORT CUDA EP. Dazu Kaltstart (Container-Start bis erster Treffer), VRAM und Image-Größe.
4. **Netzaufschlag** Pi → Erkennungsdienst über die dauerhafte WebSocket-Verbindung mit echten JPEG-Größen: p50/p95/p99 über ≥ 1.000 Frames. Vergleich (a) Container unter Docker Desktop vs. (b) derselbe Echo-Dienst nativ unter Windows. Optional (c) mirrored Mode, falls (a) auffällt. Grenze: Aufschlag ≤ 50 ms p95.
5. **kNN:** Zeit pro Abfrage inkl. `topk` und Zusammenfassen auf Karten. Dauer des Indexaufbaus für den vollen Katalog (Zielgröße: Minuten, damit ein Neuaufbau nach Katalog-Update nicht stört).

## Offene Punkte

- Ob das ONNX-Modell im DRAW2-Repo Embeddings ausgibt oder nur Logits. Für den PyTorch-Weg egal.
- Keine Zahlen zu deutschen Karten und Altkarten, weder für DRAW2 noch für DINOv2.
- Keine primäre Messung des Netzaufschlags durch Docker Desktop/WSL2.
- DRAW2-Training und Datensatz sind nicht vollständig dokumentiert (keine Genauigkeitszahlen im Repo [3]).
- Lizenzbewertungen sind technische Einschätzungen, keine Rechtsberatung.

## Quellen

1. yugioh-ar, `research/TIEMPO_REAL.md` (GPU-Messungen RTX 4070, DINOv2-Vergleich, ONNX Runtime CUDA, Indexaufbau): https://github.com/Adrian-Sandwich/yugioh-ar/blob/main/research/TIEMPO_REAL.md
2. Hugging Face, Modellkarte `HichTala/draw2` (Lizenz agpl-3.0, Basis-ViT, 96,4 M Parameter): https://huggingface.co/HichTala/draw2
3. HichTala/draw2, README und Lizenz: https://github.com/HichTala/draw2
4. yugioh-ar, `research/PLAN_VECTORES_E_INVARIANCIA.md` (768-dim Embeddings ohne Training, geplantes Feintuning, Brute-Force/IndexFlatIP): https://github.com/Adrian-Sandwich/yugioh-ar/blob/main/research/PLAN_VECTORES_E_INVARIANCIA.md
5. yugioh-ar, `research/CALIBRACION_ESCANEOS.md` (Schwellen, Ergebnisse nach Seltenheit): https://github.com/Adrian-Sandwich/yugioh-ar/blob/main/research/CALIBRACION_ESCANEOS.md
6. facebookresearch/dinov2, README (Apache-2.0, Varianten, Embedding-Dimensionen, torch.hub): https://github.com/facebookresearch/dinov2
7. GNU, Liste der Lizenzen (Apache-2.0 kompatibel mit GPLv3): https://www.gnu.org/licenses/license-list.html
8. facebookresearch/dinov3, README: https://github.com/facebookresearch/dinov3
9. DINOv3 License: https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md
10. Oquab et al., „DINOv2: Learning Robust Visual Features without Supervision“, Tab. 9: https://arxiv.org/abs/2304.07193
11. Hugging Face, Dateien von `HichTala/draw2`: https://huggingface.co/HichTala/draw2/tree/main
12. Ultralytics, README (Lizenz AGPL-3.0 / Enterprise): https://github.com/ultralytics/ultralytics
13. KevinMusgrave/pytorch-metric-learning (MIT, Losses und Miner): https://github.com/KevinMusgrave/pytorch-metric-learning
14. NVIDIA, CUDA 12.8 Release Notes (Compiler-Support SM_100, SM_101, SM_120): https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/index.html
15. NVIDIA, CUDA on WSL User Guide: https://docs.nvidia.com/cuda/wsl-user-guide/index.html
16. Docker Docs, Networking in Docker Desktop (Port-Publishing): https://docs.docker.com/desktop/features/networking/
17. NVIDIA, CUDA Toolkit Release Notes 13.4 (Treiber ≥ 580 für CUDA 13.x): https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html
18. Docker Docs, GPU support in Docker Desktop for Windows: https://docs.docker.com/desktop/features/gpu/
19. PyTorch 2.7 Release Blog (Blackwell, CUDA-12.8-Wheels): https://pytorch.org/blog/pytorch-2-7/
20. FAISS Wiki, „Guidelines to choose an index“: https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index
21. PyTorch, `RELEASE.md` (Kompatibilitätsmatrix und Release-Termine): https://github.com/pytorch/pytorch/blob/main/RELEASE.md
22. ONNX Runtime, CUDA Execution Provider (Requirements): https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html
23. ONNX Runtime PR #26230, „[CUDA] replace 90a-virtual by 90-virtual for forward compatible“: https://github.com/microsoft/onnxruntime/pull/26230
24. NVIDIA, TensorRT Support Matrix: https://docs.nvidia.com/deeplearning/tensorrt/latest/getting-started/support-matrix.html
25. ONNX Runtime, TensorRT Execution Provider (Engine- und Timing-Cache): https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html
26. ONNX Runtime, TensorRT RTX Execution Provider: https://onnxruntime.ai/docs/execution-providers/TensorRTRTX-ExecutionProvider.html
27. Microsoft Learn, „Accessing network applications with WSL“: https://learn.microsoft.com/en-us/windows/wsl/networking
28. Microsoft Learn, „Advanced settings configuration in WSL“ (`networkingMode`, `firewall`, `hostAddressLoopback`): https://learn.microsoft.com/en-us/windows/wsl/wsl-config
29. Docker Forum (Sekundärquelle), „Host networking not working on Docker Desktop in WSL2 with mirrored mode“: https://forums.docker.com/t/host-networking-not-working-on-docker-desktop-in-wsl2-with-mirrored-mode/147994
30. microsoft/WSL Issue #10683 (mirrored, Container-Ports nicht erreichbar): https://github.com/microsoft/WSL/issues/10683
31. microsoft/WSL Issue #4901 (Durchsatz, nicht Latenz): https://github.com/microsoft/WSL/issues/4901
32. FAISS, `INSTALL.md`: https://github.com/facebookresearch/faiss/blob/main/INSTALL.md
