@echo off
rem Gera o relatorio de ONTEM (dia completo) e abre no Bloco de Notas.
rem Se o relatorio de ontem ja existir completo, so abre.
setlocal EnableExtensions
chcp 65001 >nul

rem 1 = inclui o resumo do Claude (modelo Haiku); 0 = sem resumo, mais rapido e sem gastar tokens.
set "RESUMO_IA=1"

set "SCRIPT=%~dp0relatorio-tokens.js"
set "BASE=%LOCALAPPDATA%\relatorio-tokens"
if not exist "%BASE%" mkdir "%BASE%"
where node >nul 2>&1 || (echo Node.js nao encontrado. Instale com: winget install OpenJS.NodeJS.LTS & pause & exit /b 1)
if not exist "%SCRIPT%" (echo Nao achei %SCRIPT% & pause & exit /b 1)

for /f "delims=" %%i in ('powershell -NoProfile -Command "[Environment]::GetFolderPath('MyDocuments')"') do set "PASTA=%%i\Relatorios Claude"
for /f %%i in ('powershell -NoProfile -Command "(Get-Date).AddDays(-1).ToString('yyyy-MM')"') do set "MES=%%i"
for /f %%i in ('powershell -NoProfile -Command "(Get-Date).AddDays(-1).ToString('yyyy-MM-dd')"') do set "ONTEM=%%i"

echo Gerando o relatorio de ontem (%ONTEM%)...
node "%SCRIPT%" --saida "%PASTA%" --dias 1 --excluir-hoje 1 --so-faltantes 1 --resumo-ia %RESUMO_IA% --ignorar-pasta "%BASE%" --pc "%COMPUTERNAME%"
if errorlevel 1 (echo Falha ao gerar o relatorio. & pause & exit /b 1)

set "ARQ=%PASTA%\%MES%\%ONTEM%.txt"
if exist "%ARQ%" (
  start "" notepad "%ARQ%"
) else (
  echo Nenhuma sessao do Claude Code ontem neste PC.
  pause
)
