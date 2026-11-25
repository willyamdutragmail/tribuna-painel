@echo off
rem Instala o relatorio diario de uso do Claude Code neste PC.
rem Copia os arquivos, agenda a execucao diaria e roda a primeira vez.
setlocal EnableExtensions
chcp 65001 >nul

rem Horario diario da execucao. Se o PC estiver desligado, roda assim que ligar.
set "HORA=23:30"
set "DEST=%LOCALAPPDATA%\relatorio-tokens"
set "TAREFA=Relatorio de uso do Claude Code"

where node >nul 2>&1 || (echo Instale o Node.js primeiro: winget install OpenJS.NodeJS.LTS & pause & exit /b 1)

if not exist "%DEST%" mkdir "%DEST%"
copy /y "%~dp0relatorio-tokens.js" "%DEST%\" >nul || (echo ERRO ao copiar arquivos. & pause & exit /b 1)
copy /y "%~dp0relatorio-tokens.bat" "%DEST%\" >nul || (echo ERRO ao copiar arquivos. & pause & exit /b 1)
copy /y "%~dp0relatorio-agora.bat" "%DEST%\" >nul || (echo ERRO ao copiar arquivos. & pause & exit /b 1)
echo Arquivos copiados para %DEST%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$a = New-ScheduledTaskAction -Execute '%DEST%\relatorio-tokens.bat';" ^
  "$t = New-ScheduledTaskTrigger -Daily -At '%HORA%';" ^
  "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30);" ^
  "Register-ScheduledTask -TaskName '%TAREFA%' -Action $a -Trigger $t -Settings $s -Description 'Gera o relatorio diario de tokens do Claude Code em Documentos\Relatorios Claude.' -Force | Out-Null"
if errorlevel 1 (echo ERRO ao agendar a tarefa. & pause & exit /b 1)
echo Tarefa "%TAREFA%" agendada para todo dia as %HORA%.

rem Atalho na area de trabalho para gerar o relatorio de hoje na hora.
powershell -NoProfile -Command ^
  "$w = New-Object -ComObject WScript.Shell; $l = $w.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Relatorio Claude de hoje.lnk');" ^
  "$l.TargetPath = '%DEST%\relatorio-agora.bat'; $l.WorkingDirectory = '%DEST%'; $l.Save()"
echo Atalho "Relatorio Claude de hoje" criado na area de trabalho.

echo.
echo Gerando os relatorios dos ultimos 30 dias...
call "%DEST%\relatorio-tokens.bat" 30
for /f "delims=" %%i in ('powershell -NoProfile -Command "[Environment]::GetFolderPath('MyDocuments')"') do set "DOCS=%%i"
if exist "%DOCS%\Relatorios Claude" start "" "%DOCS%\Relatorios Claude"
echo.
echo Pronto. Log da ultima execucao: %DEST%\ultimo-log.txt
pause
