<#
  Alternativa sem OBS: grava SÓ a janela do jogo com ffmpeg (gdigrab por título).
  Nunca grava a área de trabalho inteira (regra do PC de environment).

  Limitação: o ffmpeg não grava o áudio de um único aplicativo no Windows. Sem som de jogo
  aqui; para vídeo com som use o OBS (gravar_obs.py, "Captura de áudio de aplicativo").
  Se a janela sair preta (jogos DX12 em modo flip), use o OBS com Windows Graphics Capture.

  Uso:
    .\gravar_ffmpeg.ps1 -Sessao C:\capturas\2026-11-21_ep01 -Duracao 600 -Janela "AbyssalSurvivors"
#>
param(
  [Parameter(Mandatory)] [string]$Sessao,
  [Parameter(Mandatory)] [string]$Janela,   # parte do título da janela do jogo
  [int]$Duracao = 600,
  [int]$Fps = 30
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Sessao | Out-Null
$saida = Join-Path $Sessao "captura.mp4"

$proc = Get-Process | Where-Object { $_.MainWindowTitle -like "*$Janela*" } | Select-Object -First 1
if (-not $proc) { throw "Janela com '$Janela' no título não encontrada" }
$titulo = $proc.MainWindowTitle

$enc = @("-c:v", "libx264", "-preset", "veryfast", "-crf", "20")
if ((ffmpeg -hide_banner -encoders 2>$null) -match "h264_nvenc") { $enc = @("-c:v", "h264_nvenc", "-preset", "p5", "-cq", "21") }
$ffArgs = @("-hide_banner", "-y", "-f", "gdigrab", "-framerate", "$Fps", "-i", "title=$titulo") + $enc +
          @("-pix_fmt", "yuv420p", "-t", "$Duracao", $saida)

$inicio = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
@{ inicio_epoch = $inicio } | ConvertTo-Json | Set-Content (Join-Path $Sessao "sessao.json")
& ffmpeg @ffArgs
$fim = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
@{ inicio_epoch = $inicio; fim_epoch = $fim; arquivo = "captura.mp4"; janela = $titulo } | ConvertTo-Json | Set-Content (Join-Path $Sessao "sessao.json")
Write-Host "ok: $saida"
