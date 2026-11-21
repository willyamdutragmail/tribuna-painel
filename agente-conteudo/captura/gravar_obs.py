#!/usr/bin/env python3
"""Grava gameplay pelo OBS (obs-websocket, já embutido no OBS 28+) — roda no PC de gameplay.

Pensado para ser chamado pelo robô que joga: inicia a gravação, devolve o horário de
início (para alinhar o log de eventos) e para quando o tempo acaba ou quando o arquivo
de parada aparece.

Pré-requisitos (uma vez):
  pip install obsws-python
  OBS > Ferramentas > Configurações do WebSocket: ativar, porta 4455, definir senha.
  OBS > Configurações > Saída > Gravação: formato mp4 (ou mkv + remux), encoder NVENC/x264.
  Cena "Gameplay" SÓ com a janela do jogo e o áudio do jogo (nunca a área de trabalho):
    - Captura de janela, método Windows Graphics Capture (ou Captura de jogo, modo janela)
    - Captura de áudio de aplicativo (Windows 11) do processo do jogo
    - áudio da área de trabalho e microfone desativados

Uso:
  python gravar_obs.py --duracao 600 --sessao C:\\capturas\\2026-11-21_ep01
  python gravar_obs.py --ate-arquivo C:\\capturas\\PARAR --sessao ...   (o robô cria PARAR para encerrar)

Saída em --sessao: sessao.json {inicio_epoch, fim_epoch, arquivo_obs}. O robô deve gravar
eventos em <sessao>/eventos.jsonl com {"ts": epoch, "tipo": "...", ...} ou {"t": seg, ...}.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sessao", type=Path, required=True, help="pasta da sessão de captura")
    ap.add_argument("--duracao", type=float, default=0, help="segundos (0 = até o arquivo de parada)")
    ap.add_argument("--ate-arquivo", type=Path, help="para quando este arquivo existir")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--porta", type=int, default=4455)
    ap.add_argument("--senha", default=os.environ.get("OBS_WS_SENHA", ""))
    a = ap.parse_args()
    if not a.duracao and not a.ate_arquivo:
        ap.error("informe --duracao e/ou --ate-arquivo")

    import obsws_python as obs

    a.sessao.mkdir(parents=True, exist_ok=True)
    cli = obs.ReqClient(host=a.host, port=a.porta, password=a.senha, timeout=10)
    if cli.get_record_status().output_active:
        cli.stop_record()
        time.sleep(2)
    if a.ate_arquivo and a.ate_arquivo.exists():
        a.ate_arquivo.unlink()

    cli.start_record()
    inicio = time.time()
    print(f"[obs] gravando desde {time.strftime('%H:%M:%S')}", flush=True)
    (a.sessao / "sessao.json").write_text(json.dumps({"inicio_epoch": inicio}))
    try:
        while True:
            time.sleep(0.5)
            if a.duracao and time.time() - inicio >= a.duracao:
                break
            if a.ate_arquivo and a.ate_arquivo.exists():
                break
    finally:
        resp = cli.stop_record()
        fim = time.time()
    arquivo = Path(resp.output_path)
    time.sleep(2)  # OBS finalizando o arquivo
    destino = a.sessao / ("captura" + arquivo.suffix)
    shutil.move(str(arquivo), destino)
    (a.sessao / "sessao.json").write_text(json.dumps(
        {"inicio_epoch": inicio, "fim_epoch": fim, "arquivo": destino.name}, indent=1))
    print(f"[obs] ok: {destino} ({fim - inicio:.0f}s)")


if __name__ == "__main__":
    main()
