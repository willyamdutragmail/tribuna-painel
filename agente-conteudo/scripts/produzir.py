#!/usr/bin/env python3
"""Monta o vídeo final a partir de um roteiro: cortes + narração + legendas.

Etapas: (1) narração TTS por cena  (2) corte/ajuste de cada cena  (3) concatenação
(4) trilha opcional  (5) legendas .srt para upload.

Regras de montagem:
  - Cada cena usa o trecho [inicio, fim] da captura, acelerado por `velocidade`.
  - Se a narração for mais longa que o trecho, o corte é estendido na captura;
    se a captura acabar, o último quadro é congelado.
  - O áudio do jogo abaixa (ducking) enquanto a narração fala.
  - Legendas da narração e `texto_tela` (letreiro) são gravadas na imagem.

Uso:
  python produzir.py roteiro.json [--saida trabalho/ep01/render] [--so-narracao]
"""
from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

from comum import exigir, hms, parse_tempo, run, sondar
from narrar import narrar_roteiro

FPS = 30
FORMATOS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}


# ---------------------------------------------------------------- legendas
def quebrar_frases(texto: str, max_chars: int) -> list[str]:
    """Divide a narração em blocos de legenda de até 2 linhas."""
    import re
    frases = [f.strip() for f in re.split(r"(?<=[.!?…])\s+", texto) if f.strip()]
    blocos: list[str] = []
    for f in frases:
        linhas = textwrap.wrap(f, max_chars)
        for i in range(0, len(linhas), 2):
            blocos.append("\\N".join(linhas[i:i + 2]))
    return blocos


def tempo_ass(t: float) -> str:
    h, r = divmod(max(0.0, t), 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def gerar_ass(destino: Path, W: int, H: int, eventos: list[tuple[float, float, str, str]]) -> None:
    vertical = H > W
    fs_leg = int(H * (0.034 if vertical else 0.05))
    fs_tit = int(H * (0.05 if vertical else 0.075))
    mv_leg = int(H * (0.22 if vertical else 0.06))
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Leg,DejaVu Sans,{fs_leg},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{max(2, fs_leg // 12)},1,2,60,60,{mv_leg},1
Style: Tit,DejaVu Sans,{fs_tit},&H0000E1FF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,{max(3, fs_tit // 10)},2,8,60,60,{int(H * 0.07)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    linhas = [f"Dialogue: 0,{tempo_ass(a)},{tempo_ass(b)},{estilo},,0,0,0,,{txt}"
              for a, b, estilo, txt in eventos]
    destino.write_text(cab + "\n".join(linhas) + "\n", encoding="utf-8")


def eventos_legenda(texto: str, ini: float, dur: float, max_chars: int) -> list[tuple[float, float, str]]:
    blocos = quebrar_frases(texto, max_chars)
    if not blocos:
        return []
    pesos = [len(b) for b in blocos]
    total = sum(pesos)
    out, t = [], ini
    for b, p in zip(blocos, pesos):
        d = dur * p / total
        out.append((t, t + d, b))
        t += d
    return out


# ---------------------------------------------------------------- filtros
def cadeia_atempo(v: float) -> str:
    partes = []
    while v > 2.0:
        partes.append("atempo=2.0")
        v /= 2.0
    while v < 0.5:
        partes.append("atempo=0.5")
        v /= 0.5
    partes.append(f"atempo={v:.4f}")
    return ",".join(partes)


def filtro_enquadrar(W: int, H: int, src_w: int, src_h: int, modo: str) -> str:
    """Leva a captura ao formato de saída. modo: 'ajustar' (barras/blur) ou 'preencher' (corta)."""
    if modo == "preencher":
        return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if abs(src_w / max(1, src_h) - W / H) < 0.02:
        return f"scale={W}:{H}"
    # fundo desfocado + imagem inteira por cima (bom para 9:16 a partir de 16:9)
    return (f"split=2[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur=20:2,eq=brightness=-0.08[bgb];[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2")


def escapar_caminho_filtro(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


# ---------------------------------------------------------------- montagem
def montar_cena(i: int, cena: dict, narr: dict, video: Path, meta: dict, cfg: dict,
                pasta: Path, primeira: bool, ultima: bool) -> dict:
    W, H = cfg["W"], cfg["H"]
    ini = parse_tempo(cena["inicio"])
    fim = parse_tempo(cena["fim"])
    vel = float(cena.get("velocidade", 1.0))
    atraso = float(cena.get("atraso_narracao", cfg["atraso_narracao"]))
    sobra = float(cena.get("respiro", cfg["respiro"]))
    nd = narr["duracao"]
    if fim <= ini:
        raise SystemExit(f"[erro] cena {i}: fim ({fim}) <= início ({ini})")

    dur_saida = (fim - ini) / vel
    precisa = atraso + nd + sobra if nd else dur_saida
    congelar = 0.0
    if precisa > dur_saida:
        extra_src = (precisa - dur_saida) * vel
        novo_fim = min(meta["duracao"], fim + extra_src)
        congelar = max(0.0, precisa - (novo_fim - ini) / vel)
        fim = novo_fim
        dur_saida = precisa

    ass = pasta / f"cena_{i:02d}.ass"
    ev = []
    if cena.get("texto_tela"):
        ev.append((0.0, min(dur_saida, float(cena.get("duracao_texto_tela", 3.0))), "Tit", cena["texto_tela"]))
    if cfg["legendas"] and nd:
        mc = 30 if H > W else 46
        ev += [(a, b, "Leg", t) for a, b, t in eventos_legenda(cena["narracao"], atraso, nd, mc)]
    gerar_ass(ass, W, H, ev)

    vf = []
    if vel != 1.0:
        vf.append(f"setpts=PTS/{vel}")
    if congelar > 0:
        vf.append(f"tpad=stop_mode=clone:stop_duration={congelar:.3f}")
    vf.append(filtro_enquadrar(W, H, meta["largura"], meta["altura"], cfg["enquadramento"]))
    vf.append(f"fps={FPS},format=yuv420p")
    if primeira:
        vf.append("fade=t=in:st=0:d=0.6")
    if ultima:
        vf.append(f"fade=t=out:st={max(0, dur_saida - 0.8):.3f}:d=0.8")
    vf.append(f"subtitles=filename='{escapar_caminho_filtro(ass)}'")

    entradas = ["-ss", f"{ini:.3f}", "-t", f"{fim - ini:.3f}", "-i", str(video)]
    if nd:
        entradas += ["-i", narr["arquivo"]]

    vol = float(cena.get("volume_jogo", cfg["volume_jogo"]))
    duck = float(cena.get("volume_jogo_sob_narracao", cfg["volume_jogo_sob_narracao"]))
    if meta["tem_audio"]:
        ga = ["[0:a]aresample=48000,aformat=channel_layouts=stereo"]
        if vel != 1.0:
            ga.append(cadeia_atempo(vel))
        ga.append("apad")
        if nd:
            a, b = atraso - 0.15, atraso + nd + 0.15
            ga.append(f"volume='if(between(t,{a:.2f},{b:.2f}),{duck},{vol})':eval=frame")
        else:
            ga.append(f"volume={vol}")
        jogo = ",".join(ga) + "[ga]"
    else:
        jogo = "anullsrc=r=48000:cl=stereo[ga]"

    fc = [f"[0:v]{','.join(vf)}[v]", jogo]
    if nd:
        ms = int(atraso * 1000)
        fc.append(f"[1:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms},"
                  f"volume={cfg['volume_narracao']},apad[na]")
        fc.append("[ga][na]amix=inputs=2:normalize=0:duration=longest[am]")
    else:
        fc.append("[ga]anull[am]")
    af = f"atrim=0:{dur_saida:.3f},afade=t=in:d=0.05,afade=t=out:st={max(0, dur_saida - 0.08):.3f}:d=0.08"
    if ultima:
        af += f",afade=t=out:st={max(0, dur_saida - 0.8):.3f}:d=0.8"
    fc.append(f"[am]{af}[a]")

    saida = pasta / f"cena_{i:02d}.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *entradas,
         "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
         "-t", f"{dur_saida:.3f}", "-c:v", "libx264", "-preset", cfg["preset"], "-crf", str(cfg["crf"]),
         "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-movflags", "+faststart", str(saida)])
    return {"cena": i, "arquivo": str(saida), "duracao": round(dur_saida, 3),
            "origem": [round(ini, 2), round(fim, 2)], "congelado": round(congelar, 2),
            "narracao_s": round(nd, 2), "atraso": atraso}


def srt_global(roteiro: dict, linha: list[dict], cfg: dict) -> str:
    out, n, t0 = [], 1, 0.0

    def ts(t):
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"

    for cena, item in zip(roteiro["cenas"], linha):
        if item["narracao_s"]:
            for a, b, txt in eventos_legenda(cena["narracao"], item["atraso"], item["narracao_s"], 46):
                out.append(f"{n}\n{ts(t0 + a)} --> {ts(t0 + b)}\n{txt.replace(chr(92) + 'N', chr(10))}\n")
                n += 1
        t0 += item["duracao"]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roteiro", type=Path)
    ap.add_argument("--saida", type=Path, help="padrão: pasta 'render' ao lado do roteiro")
    ap.add_argument("--so-narracao", action="store_true", help="só gera os áudios (para revisar)")
    ap.add_argument("--rascunho", action="store_true", help="render rápido em baixa qualidade")
    a = ap.parse_args()
    exigir("ffmpeg")

    base = a.roteiro.parent
    roteiro = json.loads(a.roteiro.read_text(encoding="utf-8"))
    saida = a.saida or base / "render"
    saida.mkdir(parents=True, exist_ok=True)
    video = Path(roteiro["video"])
    if not video.is_absolute():
        video = (base / video).resolve()
    meta = sondar(video)

    W, H = FORMATOS[roteiro.get("formato", "16:9")]
    if a.rascunho:
        W, H = W // 2, H // 2
    au = roteiro.get("audio", {})
    cfg = {
        "W": W, "H": H, "legendas": roteiro.get("legendas", True),
        "enquadramento": roteiro.get("enquadramento", "ajustar"),
        "atraso_narracao": roteiro.get("atraso_narracao", 0.35), "respiro": roteiro.get("respiro", 0.45),
        "volume_jogo": au.get("volume_jogo", 0.9), "volume_jogo_sob_narracao": au.get("volume_jogo_sob_narracao", 0.22),
        "volume_narracao": au.get("volume_narracao", 1.25),
        "crf": 28 if a.rascunho else 20, "preset": "veryfast" if a.rascunho else "medium",
    }

    print(f"[1/4] narração ({len(roteiro['cenas'])} cenas)…")
    narr = narrar_roteiro(roteiro, saida / "narracao")
    if a.so_narracao:
        return

    print(f"[2/4] montando cenas em {W}x{H}…")
    pasta = saida / "cenas"
    pasta.mkdir(exist_ok=True)
    linha = []
    n = len(roteiro["cenas"])
    for i, (cena, nr) in enumerate(zip(roteiro["cenas"], narr)):
        item = montar_cena(i, cena, nr, video, meta, cfg, pasta, i == 0, i == n - 1)
        print(f"  cena {i:02d}: {item['duracao']:5.2f}s  origem {hms(item['origem'][0])}–{hms(item['origem'][1])}"
              + (f"  (+{item['congelado']}s congelado)" if item["congelado"] else ""))
        linha.append(item)

    print("[3/4] concatenando…")
    lista = pasta / "lista.txt"
    lista.write_text("".join(f"file '{Path(x['arquivo']).name}'\n" for x in linha))
    nome = roteiro.get("arquivo_saida") or "video_final.mp4"
    final = saida / nome
    concat = saida / "_concat.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(lista), "-c", "copy", str(concat)])

    # passo final só de áudio (vídeo copiado): trilha opcional + loudness -14 LUFS (YouTube)
    total = sum(x["duracao"] for x in linha)
    lufs = au.get("loudness_lufs", -14)
    entradas, fc = ["-i", str(concat)], "[0:a]anull[mix]"
    if au.get("trilha"):
        print("[3b] mixando trilha sonora…")
        trilha = Path(au["trilha"])
        trilha = trilha if trilha.is_absolute() else (base / trilha).resolve()
        vt = au.get("volume_trilha", 0.12)
        entradas += ["-stream_loop", "-1", "-i", str(trilha)]
        fc = (f"[1:a]volume={vt},afade=t=in:d=1.5,afade=t=out:st={max(0, total - 2.5):.2f}:d=2.5[m];"
              "[0:a][m]amix=inputs=2:normalize=0:duration=first[mix]")
    fc += f";[mix]loudnorm=I={lufs}:TP=-1.5:LRA=11,aresample=48000[a]"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *entradas, "-filter_complex", fc,
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-t", f"{total:.3f}", "-movflags", "+faststart", str(final)])
    concat.unlink(missing_ok=True)

    print("[4/4] legendas .srt e linha do tempo…")
    (saida / Path(nome).with_suffix(".srt").name).write_text(srt_global(roteiro, linha, cfg), encoding="utf-8")
    (saida / "linha_do_tempo.json").write_text(json.dumps(linha, indent=1, ensure_ascii=False))
    print(f"\nPronto: {final}  ({hms(total)})")


if __name__ == "__main__":
    main()
