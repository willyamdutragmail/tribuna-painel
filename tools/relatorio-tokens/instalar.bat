@echo off
rem Instala o relatorio diario de uso do Claude Code neste PC.
rem Copia os arquivos, agenda a execucao diaria e roda a primeira vez.
setlocal EnableExtensions
chcp 65001 >nul

rem Horario diario da execucao. Se o PC estiver desligado, roda assim que ligar.
set "HORA=23:30"
set "DEST=%LOCALAPPDATA%\relatorio-tokens"
set "TAREFA=Relatorio de uso do Claude Code"

where git >nul 2>&1 || (echo Instale o Git primeiro: winget install Git.Git & pause & exit /b 1)
where node >nul 2>&1 || (echo Instale o Node.js primeiro: winget install OpenJS.NodeJS.LTS & pause & exit /b 1)

if not exist "%DEST%" mkdir "%DEST%"
copy /y "%~dp0relatorio-tokens.js" "%DEST%\" >nul || (echo ERRO ao copiar arquivos. & pause & exit /b 1)
copy /y "%~dp0relatorio-tokens.bat" "%DEST%\" >nul || (echo ERRO ao copiar arquivos. & pause & exit /b 1)
echo Arquivos copiados para %DEST%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$a = New-ScheduledTaskAction -Execute '%DEST%\relatorio-tokens.bat';" ^
  "$t = New-ScheduledTaskTrigger -Daily -At '%HORA%';" ^
  "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30);" ^
  "Register-ScheduledTask -TaskName '%TAREFA%' -Action $a -Trigger $t -Settings $s -Description 'Envia ao GitHub o relatorio diario de tokens do Claude Code.' -Force | Out-Null"
if errorlevel 1 (echo ERRO ao agendar a tarefa. & pause & exit /b 1)
echo Tarefa "%TAREFA%" agendada para todo dia as %HORA%.

echo.
echo Gerando os relatorios dos ultimos 30 dias (na primeira vez o Git pode pedir login no GitHub)...
call "%DEST%\relatorio-tokens.bat" 30
echo.
echo Pronto. Log da ultima execucao: %DEST%\ultimo-log.txt
pause
