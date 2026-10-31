"""Update-Prüfung über GitHub-Releases.

Ablauf beim Programmstart (nur in der installierten .exe):
1. https://api.github.com/repos/<repo>/releases/latest abfragen (max. 4 s).
2. Ist die Version dort neuer, muss aktualisiert werden: Setup herunterladen
   (Datei "*Setup*.exe" im Release), unsichtbar starten (/VERYSILENT) und das
   Programm beenden. Das Setup installiert über die alte Version und startet das
   Programm danach automatisch neu. Einstellungen und Runden bleiben erhalten.
Ohne Internet startet das Programm normal (ein Update kann dann nicht erzwungen werden).
"""
import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from .version import GITHUB_REPO, __version__

USER_AGENT = f"ValorantAimTrainer/{__version__}"


def parse_version(v):
    """'v1.2.10' -> (1, 2, 10). Unbekanntes -> (0,)."""
    try:
        return tuple(int(x) for x in v.strip().lstrip("vV").split("."))
    except ValueError:
        return (0,)


def is_newer(remote, local=__version__):
    return parse_version(remote) > parse_version(local)


class UpdateInfo:
    def __init__(self, version, url, size, notes):
        self.version, self.url, self.size, self.notes = version, url, size, notes


def check(repo=GITHUB_REPO, timeout=4.0):
    """Neuere Version auf GitHub? -> UpdateInfo, sonst None (auch bei Fehlern/offline)."""
    api = os.environ.get("AIM_UPDATE_API")   # nur für Tests: lokaler Server statt GitHub
    if not repo and not api:
        return None
    req = urllib.request.Request(api or f"https://api.github.com/repos/{repo}/releases/latest",
                                 headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8-sig"))
    except (OSError, ValueError):
        return None
    tag = data.get("tag_name", "")
    if not is_newer(tag):
        return None
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.lower().endswith(".exe") and "setup" in name.lower():
            return UpdateInfo(tag.lstrip("vV"), asset["browser_download_url"], asset.get("size", 0),
                              (data.get("body") or "").strip())
    return None


def download(info, progress=None, chunk=1 << 16):
    """Setup in den Temp-Ordner laden. progress(geladen, gesamt) wird laufend aufgerufen."""
    dest = Path(tempfile.gettempdir()) / f"ValorantAimTrainer-Setup-{info.version}.exe"
    req = urllib.request.Request(info.url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as fh:
        total = int(r.headers.get("Content-Length") or info.size or 0)
        done = 0
        while True:
            block = r.read(chunk)
            if not block:
                break
            fh.write(block)
            done += len(block)
            if progress:
                progress(done, total)
    if info.size and dest.stat().st_size != info.size:
        raise OSError("Download unvollständig – bitte erneut versuchen.")
    return dest


def run_installer(setup_path):
    """Setup unsichtbar starten; es ersetzt die laufende Version, sobald wir beenden."""
    subprocess.Popen([str(setup_path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                     close_fds=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
