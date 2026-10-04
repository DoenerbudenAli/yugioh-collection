# Stack-Wahl

Beide Dienste sind in **Python** geschrieben, der Client ist eine **PWA in TypeScript**. Der Hauptdienst nutzt **FastAPI** und **SQLite**, der Erkennungsdienst FastAPI mit GPU-Inferenz in **Docker auf WSL2**. Die Python-Seite ist ein **uv-Workspace mit einem Paket je Modul und je Komposition**. Das Repo steht unter **AGPL-3.0-or-later**. Wir haben uns so entschieden, weil die GPU-Erkennung ohnehin Python braucht und eine PWA ohnehin TypeScript, die Sprachgrenze also nur noch zu wählen war. Zwischen Handy und Pi gelegt, bleibt das Modul Erkennung ein Paket in einer Sprache (ADR 0001/0002), und das Eval-Set kann Erkennung und den Mehr-Bild-Konsens der Erfassung direkt im Prozess aufrufen.

## Regeln

- **Client:** Vite + React + TypeScript (strict) als Single-Page-PWA. Der Hauptdienst liefert sie als statische Dateien aus, Client und API haben also dieselbe Origin.
- **Kern frameworkfrei:** Der Kern eines Moduls nutzt eingefrorene Dataclasses. `fastapi`, `pydantic`, `sqlalchemy` und alles mit I/O sind dort verboten. Pydantic lebt nur in HTTP-Adaptern, die an der Grenze parsen statt validieren.
- **Verträge über Prozessgrenzen:**
  - Client ↔ Hauptdienst (REST): OpenAPI aus FastAPI, daraus `openapi-typescript` + `openapi-fetch`.
  - Client ↔ Hauptdienst (Scan-WebSocket): Frames binär als JPEG hoch, Zustandsereignisse als JSON runter. Die Nachrichten sind eine Pydantic-Union mit Diskriminator, daraus entstehen JSON Schema und TS-Typen.
  - Hauptdienst ↔ Erkennungsdienst: eine dauerhafte WebSocket-Verbindung mit den Nachrichtenmodellen des Moduls Erkennung auf beiden Seiten. Ein Vertragstest prüft den Remote-Client-Adapter gegen einen echten Erkennungsdienst mit Fake-Engine.
  - Generierte Dateien werden committet. Die CI erzeugt sie neu und bricht bei jeder Abweichung ab.
- **Datenhaltung:** eine SQLite-Datei im WAL-Modus. Jedes Modul hat ein eigenes Tabellen-Präfix (`sammlung_…`) und einen eigenen Alembic-Migrationszweig im Speicher-Adapter. Zugriff über SQLAlchemy 2 Core, ohne ORM. Ein Strukturtest stellt sicher, dass SQL in einem Modul nur Tabellen mit dessen Präfix anfasst.
- **Modulübergreifende Vorgänge** (z. B. Scan vermerken und Exemplar buchen) laufen in **einer** Transaktion. Die Komposition öffnet sie und reicht dieselbe Verbindung an die beteiligten Adapter.
- **Workspace:** Je Modul ein Paket (`katalog`, `sammlung`, `listen`, `erkennung`, `erfassung`), je Komposition ein Paket (`hauptdienst`, `erkennungsdienst`), daneben `web/` und `eval/`. Die GPU-Abhängigkeiten stehen nur im Extra `erkennung[gpu]` und landen nie im Image des Pi.
- **Kanten doppelt erzwungen:** als deklarierte Paketabhängigkeit in `pyproject.toml` und per import-linter. Beides wird aus der einen Regeldatei aus ADR 0001 erzeugt oder gegen sie geprüft.
- **Erkennungsdienst:** Docker-Image mit festgelegter CUDA-Version (≥ 12.8 für die RTX 5080), Docker Desktop mit WSL2-Backend und GPU-Passthrough. Den Aufschlag durch das WSL2-Netzwerk misst das Eval-Set.
- **Werkzeuge Python:** Python 3.13, uv, ruff (Lint und Format), pyright strict, import-linter, pytest + Hypothesis, mutmut. Der Mutation Score ist ein Gate, Coverage nur eine Information.
- **Werkzeuge TypeScript:** Node LTS, pnpm, `tsc --strict`, typescript-eslint (strict-type-checked), Vitest, StrykerJS, Playwright. End-to-End-Tests laufen mit Fake-Kamera (`--use-fake-device-for-media-stream` mit echten Kartenvideos).
- **Offen gelassen:** die Inferenz-Runtime (PyTorch direkt, ONNX Runtime oder TensorRT). Sie hängt an Encoder-Wahl und Messungen des Eval-Sets und bleibt hinter dem GPU-Adapter austauschbar.

## Verworfene Alternativen

- **Native Android-App:** Sie brächte eine dritte Sprache, einen eigenen Release-Pfad und eine zweite UI für Listen und Prüf-Warteschlange. Der Gewinn an Kamerakontrolle ist unbelegt. Fällt die Browser-Kamera im Eval-Set durch, wird nur die Scan-Ansicht nativ.
- **TypeScript auf dem Pi, Python nur im Erkennungsdienst:** Die Typen wären durchgängig und die Werkzeuge (Stryker, dependency-cruiser) reifer. Dafür zerfiele das Modul Erkennung in zwei Sprachen mit einem Schema als Kern, das Eval-Set erreichte den Konsens der Erfassung nur über das laufende System, und es gäbe zwei gleich schwere Harness-Stacks.
- **Kotlin/JVM oder C#/.NET auf dem Pi:** ArchUnit/PIT bzw. ArchUnitNET/Stryker.NET sind die stärksten Werkzeuge für Grenzen und Mutation Testing. Es wäre aber die dritte Sprache, und eine JVM ist mit ~1 GB freiem RAM auf dem Pi unnötig knapp.
- **Litestar statt FastAPI:** schneller und mit sauberer DI, aber kleineres Ökosystem und weniger Agentenwissen. Bei einem Nutzer ist der Durchsatz kein Engpass.
- **Server-gerenderte UI (Jinja + HTMX) mit TS-Insel für die Kamera:** Das wären zwei UI-Paradigmen, und der Vertrag zwischen Client und Server ließe sich schlechter typprüfen.
- **Postgres-Container:** ~100+ MB RAM auf dem Pi für ein Ein-Nutzer-System. **DuckDB:** analytisch und für einzelne Buchungen ungeeignet.
- **Eine SQLite-Datei je Modul:** Physisch wäre das hart getrennt, aber modulübergreifende Vorgänge wären nicht atomar. Ein Absturz zwischen „Exemplar buchen“ und „Scan vermerken“ hinterließe ein Exemplar ohne Herkunft, das „Rückgängig“ nicht findet. **`ATTACH` mehrerer Dateien** sieht wie eine Datei aus, ist im WAL-Modus über Dateigrenzen aber nicht atomar.
- **SQLAlchemy-ORM:** Lazy Loading und Identity Map verstecken SQL, damit ließe sich das Tabellen-Präfix schwer prüfen. **Rohes `sqlite3`:** Migrationen müssten wir selbst bauen.
- **gRPC/Protobuf zwischen Pi und Heimrechner:** Bei zwei Python-Enden bringt es nur Zeremonie. **AsyncAPI für den Scan-WebSocket:** Das formale Format bringt nichts, was JSON Schema aus Pydantic nicht schon liefert.
- **Ein einziges Python-Paket mit Unterordnern:** Nur der Linter schützte die Grenzen, und PyTorch/CUDA müsste man per Disziplin aus dem Pi-Image heraushalten.
- **Erkennungsdienst nativ unter Windows:** Das wäre eine andere Betriebsumgebung als Pi und CI und ohne Image aus der CI.
- **MIT/Apache-2.0:** Das schlösse DRAW2 (AGPL-3.0) aus, den mit Abstand stärksten Yu-Gi-Oh-Encoder laut Research. Die Encoder-Wahl soll das Eval-Set treffen, nicht die Lizenz. Da nur der Owner das Tool nutzt, entstehen durch die AGPL keine zusätzlichen Pflichten.
