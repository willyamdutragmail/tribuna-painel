@echo off
rem Gera o relatorio de uso do Claude Code deste PC em arquivos .txt.
rem Uso: relatorio-tokens.bat [dias]   (padrao: 2 = ontem e hoje)
setlocal EnableExtensions
chcp 65001 >nul

rem ============ CONFIGURACAO ============
rem Quantos dias para tras cada execucao recalcula.
set "DIAS=2"
rem 1 = pede ao Claude (modelo Haiku) um resumo simples do dia; 0 = sem resumo.
set "RESUMO_IA=1"
rem Pasta dos relatorios. Vazio = "Relatorios Claude" dentro de Documentos.
set "PASTA="
rem ======================================

if not "%~1"=="" set "DIAS=%~1"
set "BASE=%LOCALAPPDATA%\relatorio-tokens"
set "LOG=%BASE%\ultimo-log.txt"
set "SCRIPT=%~dp0relatorio-tokens.js"
if not exist "%BASE%" mkdir "%BASE%"
if "%PASTA%"=="" for /f "delims=" %%i in ('powershell -NoProfile -Command "[Environment]::GetFolderPath('MyDocuments')"') do set "PASTA=%%i\Relatorios Claude"

call :principal > "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
type "%LOG%"
exit /b %RC%

:principal
echo [%date% %time%] Inicio - PC %COMPUTERNAME%
where node >nul 2>&1 || (echo ERRO: Node.js nao encontrado. Instale com: winget install OpenJS.NodeJS.LTS & exit /b 1)
if not exist "%SCRIPT%" (echo ERRO: nao achei %SCRIPT% & exit /b 1)

node "%SCRIPT%" --saida "%PASTA%" --dias %DIAS% --resumo-ia %RESUMO_IA% --ignorar-pasta "%BASE%" --pc "%COMPUTERNAME%"
if errorlevel 1 (echo ERRO: falha ao gerar o relatorio. & exit /b 1)
echo Relatorios em: %PASTA%
exit /b 0
