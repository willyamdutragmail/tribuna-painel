#!/usr/bin/env python3
"""Gera a narração digital (TTS) de cada cena de um roteiro.

Motores, em ordem de preferência (o primeiro que funcionar é usado):
  edge    Microsoft Edge TTS (neural, grátis, precisa de internet: speech.platform.bing.com)
  piper   Piper (neural, offline; baixa a voz do Hugging Face na 1ª vez)
  espeak  espeak-ng (robótico, offline, último recurso)

Vozes pt-BR úteis no edge: pt-BR-AntonioNeural (masc.), pt-BR-FranciscaNeural (fem.),
pt-BR-ThalitaMultilingualNeural (fem.).

Uso:
  python narrar.py roteiro.json --saida trabalho/ep01/narracao
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import urllib.request
from pathlib import Path

from comum import duracao, run

PIPER_VOZES = {
    "faber": "pt/pt_BR/faber/medium/pt_BR-faber-medium",
    "cadu": "pt/pt_BR/cadu/medium/pt_BR-cadu-medium",
    "jeff": "pt/pt_BR/jeff/medium/pt_BR-jeff-medium",
}
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "agente-conteudo"


def tts_edge(texto: str, destino: Path, voz: str, taxa: str, tom: str) -> None:
    import edge_tts  # pip install edge-tts

    async def go():
        kw = {"rate": taxa, "pitch": tom}
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if proxy:
            kw["proxy"] = proxy
        await edge_tts.Communicate(texto, voz, **kw).save(str(destino))

    asyncio.run(go())
    if not destino.exists() or destino.stat().st_size < 1000:
        raise RuntimeError("edge-tts não gerou áudio")


def tts_piper(texto: str, destino: Path, voz: str) -> None:
    from piper import PiperVoice  # pip install piper-tts
    import wave

    nome = PIPER_VOZES.get(voz, PIPER_VOZES["faber"])
    pasta = CACHE / "piper"
    pasta.mkdir(parents=True, exist_ok=True)
    base = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    modelo = pasta / (Path(nome).name + ".onnx")
    for ext in (".onnx", ".onnx.json"):
        alvo = pasta / (Path(nome).name + ext)
        if not alvo.exists():
            urllib.request.urlretrieve(base + nome + ext, alvo)
    v = PiperVoice.load(str(modelo))
    wav = destino.with_suffix(".wav")
    with wave.open(str(wav), "wb") as w:
        v.synthesize_wav(texto, w)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), str(destino)])
    wav.unlink(missing_ok=True)


def tts_espeak(texto: str, destino: Path) -> None:
    if not shutil.which("espeak-ng"):
        raise RuntimeError("espeak-ng não instalado")
    wav = destino.with_suffix(".wav")
    run(["espeak-ng", "-v", "pt-br", "-s", "165", "-w", str(wav), texto])
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), str(destino)])
    wav.unlink(missing_ok=True)


def sintetizar(texto: str, destino: Path, cfg: dict) -> str:
    motores = cfg.get("motores") or ["edge", "piper", "espeak"]
    erros = []
    for m in motores:
        try:
            if m == "edge":
                tts_edge(texto, destino, cfg.get("voz", "pt-BR-AntonioNeural"),
                         cfg.get("taxa", "+8%"), cfg.get("tom", "+0Hz"))
            elif m == "piper":
                tts_piper(texto, destino, cfg.get("voz_piper", "faber"))
            elif m == "espeak":
                tts_espeak(texto, destino)
            else:
                raise RuntimeError(f"motor desconhecido: {m}")
            return m
        except Exception as e:  # tenta o próximo motor
            erros.append(f"{m}: {e}")
    raise SystemExit("[erro] nenhum motor de TTS funcionou:\n  " + "\n  ".join(erros))


def narrar_roteiro(roteiro: dict, saida: Path) -> list[dict]:
    saida.mkdir(parents=True, exist_ok=True)
    cfg = roteiro.get("narracao", {})
    resultado = []
    for i, cena in enumerate(roteiro["cenas"]):
        texto = (cena.get("narracao") or "").strip()
        if not texto:
            resultado.append({"cena": i, "arquivo": None, "duracao": 0.0})
            continue
        destino = saida / f"cena_{i:02d}.mp3"
        cache = destino.with_suffix(".txt")
        chave = json.dumps([texto, cfg], ensure_ascii=False, sort_keys=True)
        if destino.exists() and cache.exists() and cache.read_text(encoding="utf-8") == chave:
            motor = "cache"
        else:
            motor = sintetizar(texto, destino, cfg)
            cache.write_text(chave, encoding="utf-8")
        d = duracao(destino)
        print(f"  cena {i:02d}: {d:5.2f}s [{motor}] {texto[:70]}{'…' if len(texto) > 70 else ''}")
        resultado.append({"cena": i, "arquivo": str(destino), "duracao": d})
    return resultado


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roteiro", type=Path)
    ap.add_argument("--saida", type=Path, required=True)
    a = ap.parse_args()
    r = narrar_roteiro(json.loads(a.roteiro.read_text(encoding="utf-8")), a.saida)
    (a.saida / "narracao.json").write_text(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
