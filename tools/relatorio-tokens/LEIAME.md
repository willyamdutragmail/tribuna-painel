# Relatório diário de uso do Claude Code

Todo dia, cada PC gera um relatório do que o Claude Code fez nele e envia para um repositório no GitHub.

## O que o relatório mostra

Um arquivo por dia e por computador, em `relatorios/<NOME-DO-PC>/<AAAA-MM>/<AAAA-MM-DD>.md`, com uma cópia em `.json` com os mesmos dados:

- **O que foi feito:** resumo curto escrito pelo Claude (modelo Haiku) a partir dos pedidos, arquivos alterados e commits do dia.
- **Tokens do dia:** entrada, saída, cache criado e cache lido, no total e por modelo.
- **Esforço:** quantas respostas saíram em cada nível de esforço (low, medium, high…).
- **Por sessão:** título, projeto, branch, horário, modelo, esforço, tokens, pedidos feitos, arquivos alterados e commits do dia no repositório.

Os números vêm dos registros locais do Claude Code (`%USERPROFILE%\.claude\projects`). Por isso cada PC precisa ter a instalação. Sessões na nuvem (claude.ai/code) não entram.

## Antes de instalar

1. **Crie um repositório privado vazio** no GitHub para receber os relatórios, por exemplo `claude-uso-tokens`. Os relatórios trazem nomes de pastas, pedidos feitos ao Claude e o volume de uso, então não use um repositório público.
2. Se escolher outro nome, troque a linha `REPO_URL` no topo do `relatorio-tokens.bat`.
3. O PC precisa ter Git e Node.js:
   ```
   winget install Git.Git
   winget install OpenJS.NodeJS.LTS
   ```

## Instalar em cada PC

1. Copie a pasta `tools\relatorio-tokens` para o PC.
2. Dê dois cliques em `instalar.bat`.
3. Na primeira vez, o Git pode abrir uma janela de login do GitHub. Faça o login; depois disso, as próximas execuções acontecem sozinhas.

O instalador copia os arquivos para `%LOCALAPPDATA%\relatorio-tokens`, agenda a tarefa **Relatorio de uso do Claude Code** para todo dia às 23:30 e já gera os relatórios dos últimos 30 dias. Se o PC estiver desligado no horário, a tarefa roda assim que ele ligar.

Cada execução recalcula ontem e hoje e substitui os arquivos desses dias. O resumo do Claude só é refeito se os dados do dia mudaram, então não gasta tokens à toa (fica na casa de alguns milhares de tokens do Haiku por dia).

## Ajustes

No topo do `relatorio-tokens.bat`:

| Variável | Para quê |
|---|---|
| `REPO_URL` | Repositório que recebe os relatórios |
| `BRANCH` | Branch dos relatórios (padrão `main`) |
| `DIAS` | Quantos dias cada execução recalcula (padrão 2) |
| `RESUMO_IA` | `1` gera o resumo com o Claude; `0` usa só a lista de sessões, sem gastar tokens |

O horário fica em `HORA`, no `instalar.bat`. Depois de mudar qualquer coisa, rode o `instalar.bat` de novo.

## Rodar na hora, ver o log ou remover

- **Rodar agora:** `%LOCALAPPDATA%\relatorio-tokens\relatorio-tokens.bat`
- **Log da última execução:** `%LOCALAPPDATA%\relatorio-tokens\ultimo-log.txt`
- **Remover o agendamento:** `schtasks /Delete /TN "Relatorio de uso do Claude Code" /F`
