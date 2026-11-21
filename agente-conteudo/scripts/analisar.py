#!/usr/bin/env python3
"""Analisa um vídeo de gameplay e prepara material para o Claude interpretar.

Gera em <saida>/:
  analise.json   metadados, cortes de cena, picos de áudio, eventos do robô
  analise.md     resumo legível (o Claude lê este arquivo primeiro)
  folhas/*.jpg   folhas de contato (grade de quadros com timestamp)
  quadros/*.jpg  quadros em resolução maior nos momentos de destaque

Uso:
  python analisar.py captura.mp4 --saida trabalho/ep01 [--eventos eventos.jsonl]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from comum import exigir, hms, run, sondar

FONTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def detectar_cenas(video: Path, limiar: float) -> list[dict]:
    p = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-an",
        "-vf", f"scale=320:-2,scdet=threshold={limiar}", "-f", "null", "-",
    ])
    cenas = []
    for m in re.finditer(r"lavfi\.scd\.score:\s*([\d.]+),\s*lavfi\.scd\.time:\s*([\d.]+)", p.stderr):
        cenas.append({"t": round(float(m.group(2)), 2), "score": round(float(m.group(1)), 1)})
    return cenas


def energia_audio(video: Path, tmp: Path) -> list[float]:
    """RMS (dBFS) por segundo."""
    arq = tmp / "rms.txt"
    run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vn",
        "-af", "aresample=8000,asetnsamples=n=8000:p=0,astats=metadata=1:reset=1,"
               f"ametadata=print:key=lavfi.astats.Overall.RMS_level:file={arq}",
        "-f", "null", "-",
    ])
    valores = []
    for linha in arq.read_text().splitlines():
        if linha.startswith("lavfi.astats.Overall.RMS_level="):
            v = linha.split("=", 1)[1]
            valores.append(-90.0 if v in ("-inf", "nan") else max(-90.0, float(v)))
    arq.unlink(missing_ok=True)
    return valores


def picos(rms: list[float], n: int, distancia: int = 5) -> list[dict]:
    """Segundos mais altos que a média local, separados por `distancia` s."""
    if not rms:
        return []
    import statistics
    base = statistics.median(rms)
    candidatos = sorted(range(len(rms)), key=lambda i: rms[i], reverse=True)
    escolhidos: list[int] = []
    for i in candidatos:
        if rms[i] < base + 6:  # pelo menos 6 dB acima da mediana
            break
        if all(abs(i - j) >= distancia for j in escolhidos):
            escolhidos.append(i)
        if len(escolhidos) >= n:
            break
    return [{"t": float(i), "db": round(rms[i], 1), "acima_mediana": round(rms[i] - base, 1)}
            for i in sorted(escolhidos)]


def folhas_contato(video: Path, saida: Path, intervalo: float, colunas: int, linhas: int) -> list[dict]:
    pasta = saida / "folhas"
    pasta.mkdir(parents=True, exist_ok=True)
    for f in pasta.glob("*.jpg"):
        f.unlink()
    texto = (
        f"drawtext=fontfile={FONTE}:text='%{{pts\\:hms}}':x=w-tw-8:y=h-th-8:fontsize=26:"
        "fontcolor=yellow:box=1:boxcolor=black@0.6:boxborderw=6"
    )
    run([
        "ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(video), "-an",
        "-vf", f"fps=1/{intervalo},scale=480:-2,{texto},tile={colunas}x{linhas}:padding=4:color=black",
        "-q:v", "4", "-fps_mode", "vfr", str(pasta / "folha_%03d.jpg"),
    ])
    por_folha = colunas * linhas * intervalo
    out = []
    for i, f in enumerate(sorted(pasta.glob("*.jpg"))):
        out.append({"arquivo": str(f.relative_to(saida)), "de": hms(i * por_folha),
                    "ate": hms((i + 1) * por_folha), "de_s": i * por_folha})
    return out


def quadros(video: Path, saida: Path, tempos: list[float]) -> list[dict]:
    pasta = saida / "quadros"
    pasta.mkdir(parents=True, exist_ok=True)
    out = []
    for t in tempos:
        nome = pasta / f"t{t:07.1f}.jpg"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}",
             "-i", str(video), "-frames:v", "1", "-vf", "scale=1280:-2", "-q:v", "3", str(nome)])
        if nome.exists():
            out.append({"t": t, "hms": hms(t), "arquivo": str(nome.relative_to(saida))})
    return out


def ler_eventos(caminho: Path | None) -> list[dict]:
    """Eventos do robô: JSONL com {"t": seg_desde_inicio_gravacao, "tipo": ..., ...}."""
    if not caminho:
        return []
    sessao = caminho.parent / "sessao.json"
    inicio = json.loads(sessao.read_text()).get("inicio_epoch") if sessao.exists() else None
    eventos = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        e = json.loads(linha)
        if "t" not in e and "ts" in e and inicio is not None:
            e["t"] = round(float(e["ts"]) - inicio, 2)  # epoch -> segundos desde o início da gravação
        if "t" in e:
            eventos.append(e)
    return sorted(eventos, key=lambda e: e["t"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--eventos", type=Path, help="JSONL de eventos gerado pelo robô (opcional)")
    ap.add_argument("--intervalo", type=float, help="segundos entre quadros das folhas (padrão: automático)")
    ap.add_argument("--limiar-cena", type=float, default=12.0)
    ap.add_argument("--max-quadros", type=int, default=24)
    args = ap.parse_args()

    exigir("ffmpeg")
    args.saida.mkdir(parents=True, exist_ok=True)
    meta = sondar(args.video)
    dur = meta["duracao"]
    intervalo = args.intervalo or min(10.0, max(1.0, round(dur / 60, 1)))

    print(f"[1/5] metadados: {meta}")
    print("[2/5] detectando cortes de cena…")
    cenas = detectar_cenas(args.video, args.limiar_cena)
    print("[3/5] medindo energia do áudio…")
    rms = energia_audio(args.video, args.saida) if meta["tem_audio"] else []
    top = picos(rms, n=args.max_quadros // 2)
    print("[4/5] gerando folhas de contato…")
    folhas = folhas_contato(args.video, args.saida, intervalo, colunas=4, linhas=4)
    eventos = ler_eventos(args.eventos)

    tempos = {round(p["t"] + 0.5, 1) for p in top}
    tempos |= {round(c["t"] + 0.3, 1) for c in sorted(cenas, key=lambda c: -c["score"])[: args.max_quadros // 3]}
    tempos |= {round(float(e["t"]), 1) for e in eventos[: args.max_quadros // 3]}
    tempos = sorted(t for t in tempos if 0 <= t < dur)[: args.max_quadros]
    print(f"[5/5] extraindo {len(tempos)} quadros de destaque…")
    destaques = quadros(args.video, args.saida, tempos)

    analise = {
        "video": str(args.video.resolve()), "meta": meta, "intervalo_folhas": intervalo,
        "cenas": cenas, "picos_audio": top, "rms_por_segundo": rms,
        "eventos": eventos, "folhas": folhas, "quadros": destaques,
    }
    (args.saida / "analise.json").write_text(json.dumps(analise, ensure_ascii=False, indent=1))

    md = [f"# Análise de `{args.video.name}`", "",
          f"- Duração: **{hms(dur)}** ({dur:.1f}s) · {meta['largura']}x{meta['altura']} @ {meta['fps']} fps · áudio: {'sim' if meta['tem_audio'] else 'não'}",
          f"- Folhas de contato: {len(folhas)} (1 quadro a cada {intervalo}s, grade 4x4, timestamp no canto)", ""]
    md += ["## Folhas de contato"] + [f"- `{f['arquivo']}` — {f['de']} → {f['ate']}" for f in folhas] + [""]
    md += ["## Cortes de cena (mudança brusca de imagem)"]
    md += [f"- {hms(c['t'])} (score {c['score']})" for c in cenas[:80]] or ["- nenhum detectado"]
    md += ["", "## Picos de áudio (tiros, explosões, gritos, música alta)"]
    md += [f"- {hms(p['t'])} — {p['db']} dBFS (+{p['acima_mediana']} dB sobre a mediana)" for p in top] or ["- nenhum"]
    if eventos:
        md += ["", "## Eventos registrados pelo robô"]
        md += [f"- {hms(float(e['t']))} — {e.get('tipo', '?')}: {json.dumps({k: v for k, v in e.items() if k not in ('t', 'tipo')}, ensure_ascii=False)}" for e in eventos[:200]]
    md += ["", "## Quadros de destaque"] + [f"- `{q['arquivo']}` — {q['hms']}" for q in destaques]
    (args.saida / "analise.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nPronto: {args.saida / 'analise.md'}")


if __name__ == "__main__":
    main()
