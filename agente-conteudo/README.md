# Agente de conteúdo para jogos

Transforma gameplay em vídeo pronto para publicar: **joga → grava → interpreta → roteiriza →
corta → narra (pt-BR) → legenda**. O Claude conduz o processo pela skill
`/video-gameplay` (`.claude/skills/video-gameplay/SKILL.md`).

```
 PC de gameplay (Windows)                     Sessão na nuvem (este agente)
 ┌─────────────────────────┐                  ┌──────────────────────────────────────────┐
 │ robô joga o jogo        │                  │ receber.sh   junta as partes             │
 │ gravar_obs.py / ffmpeg  │  git (branch     │ analisar.py  cenas, picos, folhas        │
 │ eventos.jsonl (robô)    │ ─capturas/...─▶  │ Claude       interpreta + propõe roteiros│
 │ enviar.ps1              │                  │ produzir.py  cortes + TTS + legendas     │
 └─────────────────────────┘                  └──────────────────────────────────────────┘
```

## Peças

| Arquivo | Onde roda | O que faz |
|---|---|---|
| `captura/gravar_obs.py` | PC de gameplay | Inicia/para gravação no OBS via websocket; grava `sessao.json` com o horário de início (alinha os eventos do robô) |
| `captura/gravar_ffmpeg.ps1` | PC de gameplay | Alternativa sem OBS: só a janela do jogo (gdigrab), sem áudio |
| `captura/enviar.ps1` | PC de gameplay | Recomprime em 1080p, fatia em partes < 95 MB e faz push numa branch `capturas/<jogo>/<id>` |
| `scripts/receber.sh` | nuvem | Baixa a branch e junta as partes em `captura.mp4` |
| `scripts/analisar.py` | nuvem | Metadados, cortes de cena, picos de áudio, eventos, folhas de contato e quadros de destaque → `analise.md` |
| `scripts/narrar.py` | nuvem | TTS por cena: Edge TTS → Piper → espeak-ng (com cache) |
| `scripts/produzir.py` | nuvem | Monta o vídeo do roteiro: cortes, velocidade, ducking do áudio do jogo, legendas, letreiros, 16:9 / 9:16 / 1:1, trilha, −14 LUFS, `.srt` |

## Eventos do robô (recomendado)

O que mais melhora a interpretação é o robô registrar o que fez. Uma linha JSON por evento em
`eventos.jsonl` na pasta da sessão:

```json
{"ts": 1763731200.5, "tipo": "morte", "causa": "lobo", "hp": 0}
{"t": 125.0, "tipo": "coleta", "item": "madeira", "qtd": 12}
```
`ts` = epoch (convertido usando `sessao.json`) ou `t` = segundos desde o início da gravação.
Tipos úteis: `inicio_partida`, `coleta`, `construcao`, `inimigo_avistado`, `dano`, `kill`,
`morte`, `respawn`, `conquista`, `bug`, `fim_partida`.

## Roteiro (`roteiro.json`)

Veja `exemplos/roteiro_exemplo.json`. Por cena:

| campo | descrição |
|---|---|
| `inicio`, `fim` | trecho da captura (`"01:23"`, `"1:02:03.5"` ou segundos) |
| `narracao` | texto falado (vazio = sem narração, só áudio do jogo) |
| `texto_tela` | letreiro grande no topo (ex.: `"DIA 1"`) |
| `velocidade` | 1.0 normal, 2.0 acelerado |
| `atraso_narracao`, `respiro`, `volume_jogo` | ajustes finos opcionais |

Globais: `formato` (`16:9`, `9:16`, `1:1`), `enquadramento` (`ajustar` = fundo desfocado,
`preencher` = corta/zoom), `narracao.voz` (`pt-BR-AntonioNeural`, `pt-BR-FranciscaNeural`,
`pt-BR-ThalitaMultilingualNeural`), `narracao.taxa` (`+8%`), `audio.trilha` (arquivo de música).

Se a narração for maior que o trecho, o corte é estendido; se a captura acabar, o último
quadro congela (aparece em `linha_do_tempo.json` → `congelado`).

## Uso manual

```bash
pip install -r requirements.txt
cd scripts
python analisar.py captura.mp4 --saida ../trabalho/gone-survivor/ep01 --eventos eventos.jsonl
# ... escrever ../trabalho/gone-survivor/ep01/roteiro.json
python produzir.py ../trabalho/gone-survivor/ep01/roteiro.json --rascunho
python produzir.py ../trabalho/gone-survivor/ep01/roteiro.json
```

## Requisitos de rede na nuvem
- `speech.platform.bing.com` — Edge TTS (voz neural grátis).
- `huggingface.co` (+ CDN) — vozes Piper offline (opcional).
Já liberados no ambiente “Conteúdo de jogos (narração)”.

## Próximos passos possíveis
- Vozes premium (ElevenLabs/Azure) com clonagem da sua voz.
- Detecção automática de melhores momentos (modelo de visão por trecho) para vídeos longos.
- Thumbnails automáticos a partir dos quadros de destaque.
- Narração em outros idiomas (en/es) reaproveitando o mesmo roteiro.
