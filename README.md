# wallstreet

Füllt das Terminal mit Börsen- und Nachrichtenoptik: Kurstabelle, drei
Laufbänder (Gewinner, Verlierer, Schlagzeilen), Feedreader und Pressefotos
als ASCII-Art, aufgeteilt in tmux-Fenster. Die Daten sind echt.

Abgespalten aus [dustinkirkland/hollywood](https://github.com/dustinkirkland/hollywood)
(Apache-2.0), wo `wallstreet` als zweites Programm mitgeliefert wird. Dieser
Stand läuft unter macOS und Linux und nutzt neue Datenquellen, weil die
ursprünglichen nicht mehr liefern.

## Installieren und starten

    brew install tmux newsboat libcaca jp2a
    bin/wallstreet

Auf diesem Mac zusätzlich über den lokalen Tap: `brew install martin/local/wallstreet`.
Beenden mit Ctrl-C in einem beliebigen Fenster.

## Datenquellen

| Was | Woher |
|---|---|
| Kurse, Gewinner, Verlierer | `api.nasdaq.com/api/marketmovers` (ohne Schlüssel) |
| Schlagzeilen, Bilder, Feedreader | RSS-Feeds aus `share/wallstreet/newsboat.urls` (BBC, CNBC, MarketWatch, WSJ) |

Die Kurse sind die Tagesbewegungen der US-Börsen; außerhalb der Handelszeiten
steht der letzte Schlussstand da. Feeds ändert man in `newsboat.urls`, die
Datei gilt für Feedreader, Laufband und Bilder zugleich.

Abgelöst wurden Yahoo Finance (antwortet Skripten mit 429), die Märkte-Seite
des WSJ (403), die Reuters-Feeds (abgeschaltet) und die CNN-Feeds (seit 2023
ohne neue Einträge).

## Aufbau

    bin/wallstreet            startet die tmux-Sitzung und die Fenster
    lib/wallstreet/           ein Skript je Fenster
    share/wallstreet/wsdata   holt, puffert und formatiert die Daten (Python 3, nur Standardbibliothek)
    packaging/wallstreet.rb   Homebrew-Formel

`wsdata` puffert im temporären Verzeichnis (`wallstreet-cache-<uid>`): Kurse
55 Sekunden, Feeds 5 Minuten, Bilder einen Tag. Mehrere Fenster teilen sich so
eine Abfrage, und bei Netzausfall bleibt der letzte Stand stehen.

Einzeln ausprobieren:

    share/wallstreet/wsdata table
    share/wallstreet/wsdata movers up
    share/wallstreet/wsdata headlines

## Was sich gegenüber dem Original geändert hat

- Zwischendateien liegen nicht mehr in `/dev/shm` (gibt es auf macOS nicht).
- Die Programme `w3m`, `rsstail`, `ticker` und `wget` werden nicht mehr gebraucht;
  das Laufband zeichnet `wsdata marquee` selbst.
- Ctrl-C beendet die ganze Sitzung, wenn `wallstreet` sie selbst gestartet hat.
