"""Gemeinsame Einstellungen der Tests: Importpfad, Zeitlimit-Obergrenze für die App-Läufe."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Die App-Tests fahren viele Einstellungen an ihre Grenzen: jedes Modell darf höchstens so lange rechnen (Sekunden). Ohne diese Zeile gilt der Regler der App.
os.environ.setdefault("STP_MAX_SECONDS", "3")
