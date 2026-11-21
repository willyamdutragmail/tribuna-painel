"""Utilidades compartilhadas pelo pipeline de conteúdo (ffmpeg/ffprobe)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    """Executa um comando; em caso de erro mostra o final do stderr."""
    proc = subprocess.run(cmd, capture_output=capture, text=True)
    if check and proc.returncode != 0:
        tail = (proc.stderr or "")[-3000:]
        sys.stderr.write(f"\n[erro] comando falhou: {' '.join(cmd[:6])} ...\n{tail}\n")
        raise SystemExit(proc.returncode)
    return proc


def exigir(binario: str) -> None:
    if shutil.which(binario) is None:
        raise SystemExit(f"[erro] '{binario}' não encontrado no PATH")


def sondar(caminho: str | Path) -> dict:
    """Metadados do arquivo de mídia via ffprobe."""
    exigir("ffprobe")
    p = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(caminho),
    ])
    info = json.loads(p.stdout)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    fps = 30.0
    if video and video.get("avg_frame_rate", "0/0") != "0/0":
        n, d = video["avg_frame_rate"].split("/")
        fps = float(n) / float(d) if float(d) else 30.0
    return {
        "duracao": float(info["format"].get("duration", 0.0)),
        "largura": int(video["width"]) if video else 0,
        "altura": int(video["height"]) if video else 0,
        "fps": round(fps, 3),
        "tem_audio": audio is not None,
    }


def duracao(caminho: str | Path) -> float:
    return sondar(caminho)["duracao"]


def hms(seg: float) -> str:
    seg = max(0.0, seg)
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:05.2f}" if h else f"{int(m):02d}:{s:05.2f}"


def parse_tempo(v) -> float:
    """Aceita 12.5, "12.5", "01:23", "1:02:03.5"."""
    if isinstance(v, (int, float)):
        return float(v)
    partes = [float(x) for x in str(v).strip().split(":")]
    total = 0.0
    for p in partes:
        total = total * 60 + p
    return total
