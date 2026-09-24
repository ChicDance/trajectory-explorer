# Trajektorienanalyse-App: Recherche & Implementierungsplan

2026-09-18 · @Someone

## Kontext & Annahmen

"DLR UT" bezeichnet den **DLR Urban Traffic Dataset (DLR-UT)**: Trajektoriendaten von der AIM-Forschungskreuzung in Braunschweig (Ringstraße), erfasst per Stereokamera-Setup mit 20 Hz. Rund 32.300 Trajektorien motorisierter und vulnerabler Verkehrsteilnehmer, dazu Ampel-, Wetter-, Luftqualitäts- und Straßenzustandsdaten. Lizenz CC BY 4.0, frei auf Zenodo herunterladbar (\~420 MB), inkl. PDF-Dokumentation.

Annahmen für diesen Plan:

1. Die App wird nicht nur für DLR-UT gebaut, sondern für die ganze Familie ähnlich aufgebauter Drohnen-/Kamera-Trajektoriendatensätze (DLR-UT, DLR-HT, highD, inD, rounD, exiD) über austauschbare Daten-Adapter — das ist der übliche Aufbau vergleichbarer Tools und macht "wie DLR UT" zum Referenzfall statt zur einzigen Quelle.
2. "Direkt nutzbar als Demo" heißt: mindestens ein Datensatz ist ohne Registrierung ladbar und ein kleiner Ausschnitt wird mit der App ausgeliefert oder per Direktlink nachgeladen. DLR-UT eignet sich dafür am besten (kein Login nötig, CC BY 4.0), highD/inD/rounD/exiD erfordern eine Registrierung bei leveLXData.
3. Zielplattform: lokal lauffähig und auf Streamlit Community Cloud deploybar.

## Kernanforderungen an Trajektorienanalyse-Tools

Vergleichbare Tools (leveLXData-Viewer, travia, tactics2d, movingpandas-basierte Dashboards) decken durchgängig diese Bbeweereiche ab:

- **Szenenansicht**: Top-Down-Karte/Luftbild als Hintergrund, Trajektorien als Linien/Punkte darüber, Fahrzeugumrisse maßstabsgetreu.
- **Zeitliches Playback**: Zeit-Slider und Play/Pause, um den Verkehr framegenau abzuspielen statt nur statische Pfade zu zeigen.
- **Objektfilter**: nach Klasse (Pkw, Lkw, Fahrrad, Fußgänger), Zeitfenster, einzelner Objekt-ID, Fahrspur/Bewegungsrichtung.
- **Kinematik pro Objekt**: Zeitreihen für Geschwindigkeit, Beschleunigung, Richtung/Heading, teils Jerk — als Diagramm neben der Karte.
- **Aggregierte Statistiken**: Geschwindigkeitsverteilungen, Verkehrsfluss/-dichte pro Zeitintervall, Spurwechselhäufigkeit, Anzahl Objekte je Klasse.
- **Raumbezogene Verdichtung**: Heatmaps/Dichtekarten, um Häufungspunkte (z. B. Konfliktzonen an Kreuzungen) sichtbar zu machen.
- **Sicherheits-/Interaktionsmetriken**: Time-to-Collision (TTC), Time-Headway (THW), Near-Miss-Erkennung — Standard bei Kreuzungs- und Autobahndatensätzen.
- **Export**: gefilterte Trajektorien oder berechnete Metriken als CSV/GeoJSON herunterladbar.
- **Performance**: Caching und Downsampling, da einzelne Aufnahmen mehrere zehntausend Trajektorien bzw. Millionen Zeilen umfassen können.

## Öffentlich verfügbare Trajektoriendatensätze

| Datensatz | Szene | Erfassung | Format/Rate | Lizenz | Zugang |
| --- | --- | --- | --- | --- | --- |
| [DLR-UT](https://zenodo.org/records/15754836) | Innerstädtische Kreuzung, Braunschweig | Stereokameras | Trajektorien, 20 Hz | CC BY 4.0 | Direktdownload Zenodo |
| [DLR-HT](https://zenodo.org/records/18540070) | Autobahn, Braunschweig | Kameras | Trajektorien, 20 Hz | CC BY-NC-SA 4.0 | Direktdownload Zenodo |
| [highD](https://levelxdata.com/highd-dataset) | Autobahn (6 Standorte) | Drohne | CSV, \~25 Hz | Forschungslizenz | Registrierung bei leveLXData |
| inD | Stadtkreuzungen | Drohne | CSV, \~25 Hz | Forschungslizenz | Registrierung bei leveLXData |
| rounD | Kreisverkehre | Drohne | CSV, \~25 Hz | Forschungslizenz | Registrierung bei leveLXData |
| exiD | Autobahn-Ein-/Ausfahrten | Drohne | CSV, \~25 Hz | Forschungslizenz | Registrierung bei leveLXData |
| NGSIM | Autobahn/Stadtstraße, USA | Straßenkameras | CSV, 10 Hz | Public Domain | Direktdownload |
| INTERACTION | Kreuzungen/Kreisverkehre, mehrere Länder | Drohne/Infrastruktur | CSV | Forschungslizenz | Registrierung |
| pNEUMA | Innenstadt Athen | 10 Drohnen | CSV, 25 Hz | Forschungslizenz | Registrierung |

Alle Datensätze der highD-Familie und DLR-UT/HT teilen ein ähnliches Grundschema (Objekt-ID, Zeitstempel/Frame, Position, Geschwindigkeit, Beschleunigung, Objektklasse, Abmessungen), was einen gemeinsamen internen Datentyp mit datensatzspezifischen Import-Adaptern praktikabel macht. Für eine sofort nutzbare Demo ohne Login ist **DLR-UT der geeignetste Startdatensatz**.

## Funktionsumfang der Streamlit-Demo-App (Muss-Features)

**Daten & Setup**

- Mitgelieferter Beispielausschnitt aus DLR-UT (klein genug für Streamlit Cloud) als einzige Datenquelle für den MVP; kein Datei-Upload durch Nutzer.
- Datensatz-Adapter-Schicht: einheitliches internes Schema, ein Loader pro Quelle (DLR-UT zuerst, highD/inD/rounD/exiD als Erweiterung).
- Caching des Ladevorgangs (`st.cache_data`), damit Sidebar-Filter nicht bei jeder Interaktion neu einlesen.

**Szenenansicht**

- Kartenansicht mit Hintergrundbild/Luftbild der Kreuzung bzw. des Streckenabschnitts.
- Alle Trajektorien eines Zeitfensters als Linien, aktuelle Position als Punkt/Icon je Objektklasse farbcodiert.
- Zeit-Slider mit Play/Pause für Animation des Verkehrsgeschehens.

**Filter & Auswahl**

- Filter nach Objektklasse (Pkw, Lkw, Rad, Fußgänger), Zeitfenster, einzelner Objekt-ID.
- Klick/Auswahl einer Trajektorie → Detailansicht mit Geschwindigkeits-, Beschleunigungs- und Richtungsverlauf.

**Analyse & Statistik**

- Verteilungen: Geschwindigkeit, Beschleunigung, Aufenthaltsdauer je Klasse.
- Verkehrsfluss/-dichte über die Zeit (Objekte pro Minute).
- Heatmap der Aufenthaltsorte/Konfliktzonen.
- Interaktionsmetriken TTC/THW zwischen Objektpaaren, sofern im Datensatz ableitbar.

**Export & Teilen**

- Gefilterte Trajektorien/Metriken als CSV-Download.
- Screenshot/Export der aktuellen Kartenansicht.

**Demo-Tauglichkeit**

- Läuft ohne API-Keys oder Zugangsdaten; Startseite erklärt Datenquelle und Lizenz (CC BY 4.0 DLR-UT).
- Ladezeit des Beispieldatensatzes unter \~10 Sekunden beim ersten Start.

## Technischer Architekturvorschlag

**Stack**

- **Streamlit** als UI-Framework, **pydeck** (deck.gl) für die georeferenzierte Kartenansicht mit Zeitanimation, alternativ **plotly** für Zeitreihen-Charts (Geschwindigkeit/Beschleunigung) — pydeck skaliert besser bei vielen Objekten und Frames als reine Matplotlib-Animation.
- **pandas** + **geopandas**/**movingpandas** als Analyseschicht: movingpandas liefert fertige Funktionen für Geschwindigkeitsberechnung, Stop-Erkennung und Trajektoriengeneralisierung, sodass diese nicht neu implementiert werden müssen.
- **pyproj** für Koordinatentransformation, falls Datensätze lokale statt geografische Koordinaten liefern (bei highD/DLR-UT üblich).

**Empfehlung nach weiterer Recherche:** Für DLR-UT/DLR-HT gibt es bereits [TASI](https://github.com/DLR-TS/TASI) (`pip install tasi`), eine von DLR-TS selbst gepflegte Python-Bibliothek (aktiv, Release Aug. 2026, Python ≥ 3.11, Basis NumPy/Pandas/Numba). Sie bringt native Loader für DLR-UT/DLR-HT (`DLRUTDatasetManager`, `DLRTrajectoryDataset`) und fertige Surrogate-Measures-of-Safety-Metriken (u. a. TTC, DRAC) sowie einen `TrajectoryPlotter` für Matplotlib mit. Statt DLR-UT-Adapter und TTC/DRAC in `analysis/interaction.py` selbst zu implementieren, sollte Claude Code TASI als Abhängigkeit einbinden und die Streamlit-App darauf aufsetzen — das spart eigenen Adapter- und Metrik-Code und hält die App konsistent mit der DLR-eigenen Referenzimplementierung.

**Module (Vorschlag)**

- `data/adapters/` — ein Modul je Datensatz (`dlr_ut.py`, `highd.py`, …), jedes mappt Rohspalten auf ein gemeinsames internes Schema (`track_id`, `timestamp`, `x`, `y`, `speed`, `heading`, `accel`, `class`).
- `data/registry.py` — zentrale Liste verfügbarer Datensätze/Sessions inkl. Metadaten (Lizenz, Quelle, Koordinatensystem), von der Sidebar konsumiert.
- `analysis/` — Kinematik-, Aggregations- und Interaktionsmetriken (TTC/THW), unabhängig vom UI.
- `viz/` — Kartenlayer- und Chart-Bauer, getrennt von Streamlit-Callback-Code.
- `app.py` — dünne Orchestrierung: Sidebar-Steuerung, Session-State, Seitenlayout.

**Nicht-funktionale Punkte**

- `st.cache_data` für Datenladung und teure Aggregationen; `st.session_state` für Zeit-Slider/Play-Zustand.
- Downsampling-Strategie für große Sessions (z. B. nur sichtbares Zeitfenster + gefilterte Klassen rendern).
- Deployment: Streamlit Community Cloud, Beispieldaten via Git LFS oder Nachladen von Zenodo beim ersten Start statt im Repo einzuchecken.

## Abgrenzung zu bestehenden Tools

Die recherchierten Alternativen decken das Feld nur teilweise ab:

| Tool | Was es kann | Lücke |
| --- | --- | --- |
| [TraViA](https://github.com/tud-hri/travia) (TU Delft) | Desktop-GUI zur Visualisierung & Annotation von Trajektorien | Lokale Installation nötig, keine Web-Demo, keine SMoS-Sicherheitsmetriken |
| [TASI](https://github.com/DLR-TS/TASI) (DLR-TS) | Datenladen + SMoS-Metriken (TTC, DRAC) für DLR-Datensätze | Reine Python-Bibliothek, kein UI — Nutzung erfordert eigenen Code/Notebook |
| MovingPandas | Generische Bewegungsdatenanalyse (Stops, Generalisierung) | Bibliothek ohne dediziertes Verkehrs-UI, keine Sicherheitsmetriken |
| leveLXData-Skripte, `trajectory_dataset_support`, `tactics2d` | Parsing/Visualisierung einzelner Datensatzformate | Notebook-/Skript-basiert, an ein Format gebunden, kein interaktives Dashboard |
| Bisherige Streamlit-Verkehrs-Dashboards | Verkehrsvorhersage oder CV-basiertes Object-Tracking aus Video | Kein Bezug zu kuratierten Forschungs-Trajektoriendatensätzen, keine Sicherheitsanalyse |

**Die Lücke:** Es gibt kein Zero-Install-Webtool, das SMoS-Sicherheitsmetriken (TTC/DRAC) interaktiv auf einem öffentlichen Forschungsdatensatz wie DLR-UT zeigt — heute braucht man dafür Python-Kenntnisse und eigenen Notebook-Code (TASI/MovingPandas) oder eine lokale GUI-Installation (TraViA).

**Geplante Alleinstellungsmerkmale:**

1. **Conflict Explorer** — automatisch erkannte und nach Schwere sortierte kritische Interaktionen (niedrige TTC / hohe DRAC) über die gesamte Session; ein Klick springt direkt zum Zeitfenster, statt manuell durch die Aufnahme zu scrubben.
2. **Live-Risiko-Einfärbung** — Objekte werden während des Playbacks nach aktuellem TTC/DRAC-Wert eingefärbt statt nur nach Klasse — macht Risiko im Kartenbild sofort sichtbar, statt in einer separaten Zahlentabelle.
3. **Auto-generierter Safety-Report** — Ein-Klick-Download einer Session-Zusammenfassung (Anzahl Near-Misses, TTC/DRAC-Verteilungen, Top-5-Konfliktereignisse) als teilbares Artefakt.
4. **Zero-Install-Zugang** — vollständig im Browser nutzbar, keine Python-Kenntnisse nötig — der klare Unterschied zu TraViA (Desktop-GUI) und TASI/MovingPandas (reine Bibliotheken).

## Implementierungsplan für Claude Code

**Phase 0 – Projektgerüst**

1. `uv`/`venv`-Projekt anlegen, Abhängigkeiten: `streamlit`, `pandas`, `geopandas`, `movingpandas`, `pydeck`, `plotly`, `pyproj`.
2. Ordnerstruktur (`app.py`, `data/adapters/`, `data/registry.py`, `analysis/`, `viz/`, `sample_data/`) anlegen.
3. `sample_data/dlr_ut/` mit einem kleinen, eingecheckten Ausschnitt der DLR-UT-Rohdaten (wenige Minuten, wenige hundert Trajektorien) für Offline-Demo befüllen; Download-Skript für den vollen Datensatz separat halten.

**Phase 1 – DLR-UT-Adapter & internes Schema** 4. `data/adapters/dlr_ut.py`: Rohdaten einlesen, auf internes Schema mappen (`track_id`, `timestamp`, `x`, `y`, `speed`, `accel`, `heading`, `class`, `width`, `length`). 5. `data/registry.py`: Datensatz-Eintrag für DLR-UT (Pfad, Lizenztext, Koordinatensystem, verfügbares Zeitfenster). 6. Unit-Test: Adapter lädt Beispieldaten korrekt, Schema-Spalten und Typen stimmen.

*Revidiert:* Schritte 4–5 entfallen weitgehend — `tasi.DLRUTDatasetManager` übernimmt das Laden/Mapping direkt, `data/registry.py` referenziert nur noch Pfad und Lizenzmetadaten.

**Phase 2 – Kernvisualisierung** 7. `viz/scene_map.py`: pydeck-Layer für Hintergrundbild + Trajektorienlinien + aktuelle Objektpositionen. 8. `app.py`: Sidebar mit Datensatzauswahl, Zeit-Slider, Play/Pause-Button (`st.session_state` für laufende Animation). 9. Objektklassen-Filter und Farbcodierung je Klasse.

**Phase 3 – Analyse-Features** 10. `analysis/kinematics.py`: Geschwindigkeits-/Beschleunigungs-/Richtungsverläufe je Objekt (nutzt movingpandas, wo passend). 11. `analysis/aggregates.py`: Verteilungen, Verkehrsfluss über Zeit, Heatmap-Datengrundlage. 12. `analysis/interaction.py`: TTC/THW zwischen Objektpaaren (mind. für direkt folgende Fahrzeuge). 13. Detailansicht: Klick/Auswahl einer Trajektorie → Plotly-Charts für deren Kinematik.

*Revidiert:* TTC/DRAC aus `tasi` übernehmen statt in `analysis/interaction.py` neu zu implementieren; eigener Code bleibt auf Aggregationen/Visualisierungslogik beschränkt, die TASI nicht mitbringt.

**Phase 3.5 – Differenzierende Sicherheitsanalyse-Features** (siehe "Abgrenzung zu bestehenden Tools")

13a. Conflict Explorer: Objektpaare je Zeitfenster nach minimalem TTC/maximalem DRAC ranken, als sortierbare Liste mit Sprung-Link zum jeweiligen Zeitpunkt im Slider.

13b. Live-Risiko-Einfärbung: pydeck-Layer ergänzen, der Objekte statt/zusätzlich zur Klassenfarbe nach aktuellem TTC/DRAC-Schwellenwert einfärbt (z. B. grün/gelb/rot).

13c. Safety-Report-Export: `st.download_button` für eine generierte Zusammenfassung (Near-Miss-Anzahl, Verteilungen, Top-5-Konflikte) als PDF oder Markdown.

**Phase 4 – Export & Demo-Politur** 14. CSV-Export gefilterter Daten/Metriken über `st.download_button`. 15. Startseiten-Info: Datenquelle, Lizenz (CC BY 4.0), Link zu DLR-UT auf Zenodo. 16. Performance-Pass: Caching prüfen, Downsampling bei großen Zeitfenstern testen.

**Phase 5 – Erweiterbarkeit (optional, nach MVP)** 17. Zweiten Adapter (z. B. highD) ergänzen, um die Adapter-Abstraktion zu verifizieren. 18. Eigene-Daten-Upload (CSV im internen Schema) als Alternative zu den registrierten Datensätzen. 19. Deployment auf Streamlit Community Cloud, README mit Setup- und Lizenzhinweisen.

Empfehlung: Claude Code arbeitet die Phasen 0–4 als MVP-Sprint ab (lauffähige Demo ausschließlich mit DLR-UT); Phase 5 folgt danach als eigener Auftrag.

## Hosting-Optionen (kostenlos) & Empfehlung fürs Portfolio

| Plattform | Kosten | Verhalten | Eignung |
| --- | --- | --- | --- |
| **Streamlit Community Cloud** | Kostenlos, kein Kreditkarte nötig | \~1 GB RAM/App, schläft nach Inaktivität, weckt automatisch beim Aufruf (kurzer Kaltstart) | Erste Wahl: nativ für Streamlit, Deploy per Klick direkt aus dem GitHub-Repo, Standard-"Open in Streamlit"-Badge in Portfolios |
| **Hugging Face Spaces (CPU Basic)** | Kostenlos | 2 vCPU / 16 GB RAM, schläft nach Inaktivität, Speicher nicht persistent (hier egal, da nur statische Beispieldaten) | Gute Alternative/Zweit-Hosting, erreicht zusätzlich die ML/Data-Science-Community auf HF |
| Render / Railway / Fly.io (Free Tier) | Meist Kreditkarte hinterlegt, Nutzungslimits, teils Abrechnung bei Überschreitung | — | Für einen einfachen Showcase unnötig komplex und mit Kostenrisiko |
| GitHub Pages | Kostenlos | Nur statisches Hosting | Kein Python-Backend → für Streamlit nicht nutzbar |

**Sicherheitsrisiken sind bei diesem Projekt gering**, weil kein Datei-Upload vorgesehen ist, keine Secrets/API-Keys im Code stehen, es keine Schreibzugriffe gibt und DLR-UT bereits anonymisierte, offen lizenzierte Daten sind (CC BY 4.0 — Attribution im Footer/README ist Pflicht, aber ein Lizenz- kein Sicherheitsthema). Relevant bleibt nur: Bei viel Traffic kann die App auf dem 1-GB-RAM-Tier neu starten (unkritisch für einen Portfolio-Link, Caching aus dem Architekturabschnitt hilft); ein echtes Kostenrisiko (automatische Abrechnung) besteht nur bei Pay-as-you-go-Plattformen wie GCP Cloud Run/AWS/Fly.io — bei Streamlit Cloud und HF Spaces (Free Tier) gibt es das nicht, die App wird höchstens gedrosselt oder schläft.

**Empfehlung:** Da das Ziel eine Referenz im GitHub-Repo ist, lohnt sich beides mit minimalem Zusatzaufwand:

1. App trotzdem auf **Streamlit Community Cloud** deployen (kostenlos, \~10 Minuten, nur GitHub-Login) — liefert einen klickbaren Live-Link im README.
2. Zusätzlich ein kurzes **GIF (10–15 s, < 5 MB)** im README einbetten, das Playback, Conflict Explorer und Risiko-Einfärbung zeigt. Das GIF ist das, was die meisten Betrachter tatsächlich sehen (viele klicken nicht durch) und funktioniert auch, wenn die Cloud-App gerade schläft/kalt startet.
3. Live-Badge + GIF zusammen sind Standard in Portfolio-Repos und kosten kaum mehr Aufwand als nur ein GIF.

## Offene Fragen

- [x] MVP-Scope: **nur DLR-UT**, Adapter-Architektur bleibt für spätere Datensätze vorbereitet.
- [x] Kein Nutzer-Upload eigener Daten — nur vordefinierte, geprüfte Datensätze.
- [x] UI-Sprache: **Englisch**.
- [x] Deployment: **MVP zuerst lokal lauffähig machen, dann kostenlos auf Streamlit Community Cloud deployen (siehe Hosting-Abschnitt) + kurzes GIF im README für den Portfolio-Auftritt**.
