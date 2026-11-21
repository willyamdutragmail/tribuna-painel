<#
  Envia uma sessão de captura do PC de gameplay para o agente de conteúdo (nuvem).

  Transporte: um repositório Git dedicado a capturas (privado), uma branch por sessão.
  O vídeo é recomprimido em 1080p e fatiado em partes < 95 MB (limite do GitHub é 100 MB);
  o agente na nuvem baixa a branch e junta as partes (receber.sh).

  Uso (na pasta do clone do repositório de capturas):
    .\enviar.ps1 -Sessao C:\capturas\2026-11-21_ep01 -Repo C:\Dev\gone-survivor-conteudo -Jogo gone-survivor
#>
param(
  [Parameter(Mandatory)] [string]$Sessao,
  [Parameter(Mandatory)] [string]$Repo,
  [string]$Jogo = "gone-survivor",
  [int]$Altura = 1080,
  [int]$MinutosPorParte = 4
)
$ErrorActionPreference = "Stop"
$id = Split-Path $Sessao -Leaf
$branch = "capturas/$Jogo/$id"
$destino = Join-Path $Repo "capturas/$Jogo/$id"

Push-Location $Repo
git fetch origin main 2>$null
git checkout -B $branch origin/main
New-Item -ItemType Directory -Force -Path $destino | Out-Null

$video = Get-ChildItem $Sessao -Filter "captura.*" | Select-Object -First 1
$enc = @("-c:v", "libx264", "-preset", "medium", "-crf", "24")
if ((ffmpeg -hide_banner -encoders 2>$null) -match "h264_nvenc") { $enc = @("-c:v", "h264_nvenc", "-preset", "p6", "-cq", "26") }
$seg = $MinutosPorParte * 60
& ffmpeg -hide_banner -y -i $video.FullName -vf "scale=-2:$Altura,fps=30" @enc -pix_fmt yuv420p `
  -c:a aac -b:a 160k -f segment -segment_time $seg -reset_timestamps 1 (Join-Path $destino "parte_%03d.mp4")

foreach ($f in Get-ChildItem $destino -Filter "parte_*.mp4") {
  if ($f.Length -gt 95MB) { throw "$($f.Name) passou de 95 MB; rode de novo com -MinutosPorParte menor" }
}
foreach ($extra in "sessao.json", "eventos.jsonl", "notas.md") {
  $p = Join-Path $Sessao $extra
  if (Test-Path $p) { Copy-Item $p $destino }
}
git add $destino
git commit -m "Captura $Jogo $id"
git push -u origin $branch
Pop-Location
Write-Host "Enviado: branch $branch"
