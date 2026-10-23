"""Gemeinsame Basis aller Importer.

Fehlerstrategie (zweistufig):

* **Fatal** (:class:`SourceError`): Datei fehlt, ist kein gültiges Format oder hat nicht die
  erwarteten Spalten. Ohne verlässliche Quelle ist kein Abgleich sinnvoll.
* **Zeilenfehler** (:class:`ImportIssue`): eine einzelne Zeile ist unlesbar. Die Zeile wird
  übersprungen, der Rest läuft weiter, und das Problem steht im Bericht – so geht kein Datensatz
  *stillschweigend* verloren.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ..models import Status, Transaction


class SourceError(Exception):
    """Eine Quelle kann gar nicht gelesen werden (fatal)."""


@dataclass(frozen=True)
class ImportIssue:
    """Eine Meldung beim Einlesen.

    Konnte bei einer fehlerhaften Zeile noch die Referenz gelesen werden (``key`` gesetzt), lässt sich der
    Datensatz der Gegenseite als "nicht prüfbar" kennzeichnen statt fälschlich als "fehlt". Ohne lesbare
    Referenz (``key`` leer) sind alle "fehlt"-Befunde der betroffenen Seite nur vorläufig.
    """

    source: str
    location: str                    # "Zeile 7", "transactions[3]", "id=1017"
    severity: str                    # "error" (Zeile übersprungen) | "warning" (übernommen, aber auffällig)
    message: str
    reference: str | None = None     # Roh-Referenz, falls lesbar
    provider: str | None = None      # "A"/"B", falls bekannt
    key: str = ""                    # Abgleichsschlüssel nach der ID-Regel des Anbieters, falls lesbar


@dataclass
class ImportResult:
    source: str
    path: str
    transactions: list[Transaction] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)
    rows_read: int = 0

    @property
    def errors(self) -> list[ImportIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ImportIssue]:
        return [i for i in self.issues if i.severity == "warning"]


class Importer(ABC):
    """Liest eine Quelle und liefert normalisierte :class:`Transaction`-Objekte.

    Neue Quelle anbinden = neue Unterklasse, die ``read`` implementiert – der Rest der
    Pipeline bleibt unverändert.
    """

    source: str                      # technischer Name, z. B. "provider_a"
    provider: str | None = None      # "A"/"B" für Anbieterdateien

    @abstractmethod
    def read(self, path: str | Path) -> ImportResult: ...

    @staticmethod
    def check_file(path: str | Path) -> Path:
        file = Path(path)
        if not file.is_file():
            raise SourceError(f"Datei nicht gefunden: {file}")
        return file


def map_status(raw: object, mapping: dict[str, Status]) -> tuple[Status, str | None]:
    """Quellstatus -> :class:`Status`. Unbekannte Werte werden ``UNKNOWN`` plus Warnung (kein Absturz)."""
    text = str(raw or "").strip()
    status = mapping.get(text.casefold())
    if status is not None:
        return status, None
    return Status.UNKNOWN, f"unbekannter Status {text!r} – als UNKNOWN übernommen"
