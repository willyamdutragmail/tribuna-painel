#!/usr/bin/env bash
# Baixa uma sessão de captura enviada pelo PC de gameplay (enviar.ps1) e junta as partes.
#
# Uso: receber.sh <caminho-do-clone-do-repo-de-capturas> <jogo> <id-sessao> <pasta-trabalho>
#  ex: receber.sh ~/gone-survivor-conteudo gone-survivor 2026-11-21_ep01 trabalho/ep01
set -euo pipefail
REPO=$1; JOGO=$2; ID=$3; OUT=$4
BRANCH="capturas/$JOGO/$ID"
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
cd "$REPO"
for i in 1 2 3 4; do git fetch origin "$BRANCH" && break || sleep $((2**i)); done
SRC=$(mktemp -d)
git --work-tree="$SRC" checkout FETCH_HEAD -- "capturas/$JOGO/$ID"
DIR="$SRC/capturas/$JOGO/$ID"
ls "$DIR"/parte_*.mp4 | sort | sed "s/.*/file '&'/" > "$DIR/lista.txt"
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$DIR/lista.txt" -c copy "$OUT/captura.mp4"
for f in sessao.json eventos.jsonl notas.md; do [ -f "$DIR/$f" ] && cp "$DIR/$f" "$OUT/"; done
git reset -q   # desfaz o índice alterado pelo checkout acima
rm -rf "$SRC"
echo "ok: $OUT/captura.mp4"
