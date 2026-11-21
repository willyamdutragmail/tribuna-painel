<#
  Alternativa sem OBS: grava a tela do PC de gameplay com ffmpeg (ddagrab = Desktop
  Duplication, leve e acelerado por GPU; requer ffmpeg 6+ no PATH).

  Áudio: o ffmpeg não captura o som do sistema sozinho no Windows. Use um dispositivo
  dshow — "Mixagem estéreo"/"Stereo Mix" (ativar em Som > Gravação) ou o
  "virtual-audio-capturer" do pacote screen-capture-recorder. Liste com:
     ffmpeg -list_devices true -f dshow -i dummy

  Uso:
    .\gravar_ffmpeg.ps1 -Sessao C:\capturas\2026-11-21_ep01 -Duracao 600 -Audio "Stereo Mix (Realtek(R) Audio)"
#>
param(
  [Parameter(Mandatory)] [string]$Sessao,
  [int]$Duracao = 600,
  [string]$Audio = "",
  [int]$Fps = 30,
  [int]$Monitor = 0
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Sessao | Out-Null
$saida = Join-Path $Sessao "captura.mp4"

$ffArgs = @("-hide_banner", "-y", "-filter_complex", "ddagrab=output_idx=${Monitor}:framerate=${Fps},hwdownload,format=bgra[v]")
if ($Audio) { $ffArgs += @("-f", "dshow", "-i", "audio=$Audio", "-map", "0:a") }
$ffArgs += @("-map", "[v]")

# NVENC se houver GPU NVIDIA; senão x264
$enc = @("-c:v", "libx264", "-preset", "veryfast", "-crf", "20")
if ((ffmpeg -hide_banner -encoders 2>$null) -match "h264_nvenc") { $enc = @("-c:v", "h264_nvenc", "-preset", "p5", "-cq", "21") }
$ffArgs += $enc + @("-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", "$Duracao", $saida)

$inicio = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
@{ inicio_epoch = $inicio } | ConvertTo-Json | Set-Content (Join-Path $Sessao "sessao.json")
& ffmpeg @ffArgs
$fim = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
@{ inicio_epoch = $inicio; fim_epoch = $fim; arquivo = "captura.mp4" } | ConvertTo-Json | Set-Content (Join-Path $Sessao "sessao.json")
Write-Host "ok: $saida"
