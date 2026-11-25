# Relatório diário de uso do Claude Code

Todo dia, o PC gera um relatório em texto do que o Claude Code fez nele. Fica tudo no próprio computador, sem enviar nada para lugar nenhum.

## Onde ficam os relatórios

Em **Documentos\Relatorios Claude\<AAAA-MM>\<AAAA-MM-DD>.txt**, um arquivo por dia, que abre no Bloco de Notas.

## O que o relatório mostra

- **O que foi feito:** resumo curto escrito pelo Claude (modelo Haiku) a partir dos pedidos, arquivos alterados e commits do dia.
- **Tokens do dia:** entrada, saída, cache criado e cache lido, no total e por modelo.
- **Esforço:** quantas respostas saíram em cada nível de esforço (low, medium, high…).
- **Por sessão:** título, projeto, branch, horário, modelo, esforço, tokens, pedidos feitos, arquivos alterados e commits do dia no repositório.

Os números vêm dos registros locais do Claude Code (`%USERPROFILE%\.claude\projects`), então cada PC mostra só o que rodou nele. Sessões na nuvem (claude.ai/code) não entram.

## Instalar

1. O PC precisa ter Node.js: `winget install OpenJS.NodeJS.LTS`
2. Extraia o zip e dê dois cliques em `instalar.bat`.

O instalador copia os arquivos para `%LOCALAPPDATA%\relatorio-tokens`, agenda a tarefa **Relatorio de uso do Claude Code** para todo dia às 23:30, gera os relatórios dos últimos 30 dias e abre a pasta. Se o PC estiver desligado no horário, a tarefa roda assim que ele ligar.

Cada execução recalcula ontem e hoje e substitui os arquivos desses dias. O resumo do Claude só é refeito se os dados do dia mudaram (alguns milhares de tokens do Haiku por dia).

## Testar sem instalar

No PowerShell, dentro da pasta extraída:

```
.\relatorio-tokens.bat 3
```

## Ajustes

No topo do `relatorio-tokens.bat`:

| Variável | Para quê |
|---|---|
| `DIAS` | Quantos dias cada execução recalcula (padrão 2) |
| `RESUMO_IA` | `1` gera o resumo com o Claude; `0` usa só a lista de sessões, sem gastar tokens |
| `PASTA` | Outra pasta para os relatórios (vazio = Documentos\Relatorios Claude) |

O horário fica em `HORA`, no `instalar.bat`. Depois de mudar qualquer coisa, rode o `instalar.bat` de novo.

## Log e remoção

- **Log da última execução:** `%LOCALAPPDATA%\relatorio-tokens\ultimo-log.txt`
- **Remover o agendamento:** `schtasks /Delete /TN "Relatorio de uso do Claude Code" /F`
