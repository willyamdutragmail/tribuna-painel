# Relatório diário de uso do Claude Code

Todo dia, o PC gera um relatório em texto do que o Claude Code fez nele no dia anterior. Fica tudo no próprio computador, sem enviar nada para lugar nenhum.

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

O instalador copia os arquivos para `%LOCALAPPDATA%\relatorio-tokens`, agenda a tarefa **Relatorio de uso do Claude Code** para todo dia às 08:00, cria o atalho **Relatorio Claude de hoje** na área de trabalho, gera os relatórios dos últimos 30 dias e abre a pasta. Se o PC estiver desligado no horário, a tarefa roda assim que ele ligar.

A tarefa gera o relatório de **ontem**, com o dia já completo. Se o PC ficou desligado por alguns dias, ela também gera os dias da última semana que ficaram sem relatório. Dias que já têm relatório completo nunca são refeitos. O resumo do Claude gasta alguns milhares de tokens do Haiku por dia.

## Relatório de hoje, na hora

Dê dois cliques em `relatorio-agora.bat` (ou no atalho **Relatorio Claude de hoje** que o instalador cria na área de trabalho). Ele gera o relatório da 0h até o momento e abre no Bloco de Notas. Esse relatório fica marcado como parcial, e a tarefa do dia seguinte o substitui pela versão completa. Para ficar mais rápido e sem gastar tokens, troque `RESUMO_IA=1` por `0` no topo do arquivo.

## Testar sem instalar

No PowerShell, dentro da pasta extraída:

```
.\relatorio-tokens.bat 3
```

## Ajustes

No topo do `relatorio-tokens.bat`:

| Variável | Para quê |
|---|---|
| `DIAS` | Até quantos dias para trás procurar dias sem relatório (padrão 7) |
| `RESUMO_IA` | `1` gera o resumo com o Claude; `0` usa só a lista de sessões, sem gastar tokens |
| `PASTA` | Outra pasta para os relatórios (vazio = Documentos\Relatorios Claude) |

O horário fica em `HORA`, no `instalar.bat`. Depois de mudar qualquer coisa, rode o `instalar.bat` de novo.

## Log e remoção

- **Log da última execução:** `%LOCALAPPDATA%\relatorio-tokens\ultimo-log.txt`
- **Remover o agendamento:** `schtasks /Delete /TN "Relatorio de uso do Claude Code" /F`
