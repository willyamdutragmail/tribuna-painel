---
name: video-gameplay
description: Agente de conteúdo para jogos. Pega uma captura de gameplay (gravada pelo robô no PC de gameplay ou enviada pelo usuário), interpreta o que acontece no vídeo, propõe roteiros, monta o vídeo com os cortes do roteiro e faz narração digital em pt-BR com legendas. Use quando o usuário pedir vídeo, short, roteiro, corte, narração ou conteúdo de gameplay (ex.: Gone Survivor, NexusBound).
---

# Agente de conteúdo de gameplay

Ferramentas em `agente-conteudo/` (leia `agente-conteudo/README.md` para detalhes).
Trabalhe em `agente-conteudo/trabalho/<jogo>/<id>/` (fora do git). Tudo em pt-BR.

## 0. Preparar (uma vez por sessão)
```bash
pip install -q -r agente-conteudo/requirements.txt
which ffmpeg ffprobe || apt-get install -y ffmpeg
```
Narração usa Edge TTS (precisa do host `speech.platform.bing.com` liberado); cai para
Piper (huggingface.co) e por último espeak-ng.

## 1. Obter a captura
Uma destas fontes, nesta ordem:
- **Arquivo já presente** (usuário mandou/indicou um caminho).
- **Repositório de capturas**: o PC de gameplay envia com `captura/enviar.ps1` para a branch
  `capturas/<jogo>/<id>`. Baixe com
  `agente-conteudo/scripts/receber.sh <clone> <jogo> <id> agente-conteudo/trabalho/<jogo>/<id>`.
- **Pedir ao PC de gameplay para jogar e gravar**: a sessão do PC de gameplay é uma sessão
  Remote Control (ex.: “GOne Survivor - Gameplay”). Ache-a com `list_sessions` e, **só com o
  OK do usuário**, mande via `send_message` algo como:
  > Rode o robô no Gone Survivor por ~10 min com foco em <objetivo>. Grave com
  > `python agente-conteudo/captura/gravar_obs.py --sessao C:\capturas\<id> --duracao 600`,
  > registre eventos em `C:\capturas\<id>\eventos.jsonl` ({"ts": epoch, "tipo": ...}) e envie
  > com `enviar.ps1 -Sessao C:\capturas\<id> -Repo <clone> -Jogo gone-survivor`. Responda com o id.
  Não interrompa uma sessão que está trabalhando sem o usuário pedir.

## 2. Analisar e interpretar
```bash
cd agente-conteudo/scripts
python analisar.py ../trabalho/<jogo>/<id>/captura.mp4 --saida ../trabalho/<jogo>/<id> \
  [--eventos ../trabalho/<jogo>/<id>/eventos.jsonl]
```
Depois:
1. Leia `analise.md` (cortes de cena, picos de áudio, eventos do robô).
2. **Olhe todas as folhas de contato** (`folhas/*.jpg`, com Read) — timestamp no canto inferior
   direito de cada quadro. Para trechos importantes, olhe `quadros/*.jpg` ou extraia mais:
   `ffmpeg -ss 00:01:23 -i captura.mp4 -frames:v 1 -vf scale=1280:-2 q.jpg`.
3. Escreva `interpretacao.md`: linha do tempo com o que acontece (exploração, coleta, combate,
   morte, conquista, bug engraçado, momento tenso), o estado do HUD (vida, recursos) e os
   **momentos fortes** com início/fim precisos. Diga o que é inferido e o que é certo.
   Se o vídeo for longo (> 20 min), aumente `--intervalo` e depois refine só os trechos bons.

## 3. Propor roteiros
Apresente ao usuário **2–3 propostas** curtas, cada uma com: formato (Short 9:16 de 30–60 s,
ou vídeo 16:9 de 3–10 min), título, gancho dos 3 primeiros segundos, estrutura em cenas com
timestamps e o tom da narração. Recomende uma. Boas práticas:
- Gancho forte primeiro (pode ser um flash-forward do clímax: morte, chefe, susto).
- Arco simples: contexto → escalada → clímax → desfecho/CTA.
- Narração conversacional, 1ª pessoa, frases curtas; ~2,5 palavras por segundo.
  Deixe momentos sem narração (`"narracao": ""`) para o áudio do jogo respirar no clímax.
- Short: corte a cada 2–4 s, cenas de 1–2 frases; vídeo longo: acelere trechos parados
  (`"velocidade": 1.5–3`).
- Não invente fatos do jogo que não aparecem no vídeo; nomes de itens/inimigos só se visíveis
  ou nos eventos.

## 4. Montar
Após o usuário escolher (ou pedir para seguir), grave `roteiro.json` na pasta da sessão
(formato em `agente-conteudo/exemplos/roteiro_exemplo.json`) e rode:
```bash
python produzir.py ../trabalho/<jogo>/<id>/roteiro.json --rascunho   # rápido, metade da resolução
python produzir.py ../trabalho/<jogo>/<id>/roteiro.json              # final 1080p
```
Saída em `render/`: `video_final.mp4` (ou `arquivo_saida`), `.srt`, `linha_do_tempo.json`.

## 5. Revisar antes de entregar
- Extraia quadros do resultado (início de cada cena, ver `linha_do_tempo.json`) e confira com
  Read: letreiros cabem na tela, legenda não cobre HUD importante, cortes no momento certo.
- Confira `congelado` > 1 s na linha do tempo → narração longa demais para a cena: encurte o
  texto ou estenda o corte.
- Loudness final deve estar ~ −14 LUFS (`ffmpeg -i video.mp4 -af ebur128 -f null -`).
- Entregue com `SendUserFile` (vídeo + .srt) e um resumo: duração, cenas, sugestão de título,
  descrição e hashtags para YouTube/TikTok.
- Ajustes do usuário → edite `roteiro.json` e renderize de novo (a narração tem cache por cena).
