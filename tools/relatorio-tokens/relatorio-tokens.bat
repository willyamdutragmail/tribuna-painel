@echo off
rem Gera o relatorio de uso do Claude Code deste PC e envia para o GitHub.
rem Uso: relatorio-tokens.bat [dias]   (padrao: 2 = ontem e hoje)
setlocal EnableExtensions
chcp 65001 >nul

rem ============ CONFIGURACAO (edite antes de instalar) ============
rem Repositorio que recebe os relatorios. Use um repositorio PRIVADO.
set "REPO_URL=https://github.com/willyamdutragmail/claude-uso-tokens.git"
rem Branch onde os relatorios sao gravados.
set "BRANCH=main"
rem Quantos dias para tras cada execucao recalcula.
set "DIAS=2"
rem 1 = pede ao Claude (modelo Haiku) um resumo simples do dia; 0 = sem resumo.
set "RESUMO_IA=1"
rem ================================================================

if not "%~1"=="" set "DIAS=%~1"
set "BASE=%LOCALAPPDATA%\relatorio-tokens"
set "REPO_DIR=%BASE%\repo"
set "LOG=%BASE%\ultimo-log.txt"
set "SCRIPT=%~dp0relatorio-tokens.js"
if not exist "%BASE%" mkdir "%BASE%"

call :principal > "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
type "%LOG%"
exit /b %RC%

:principal
echo [%date% %time%] Inicio - PC %COMPUTERNAME%
where git >nul 2>&1 || (echo ERRO: git nao encontrado. Instale com: winget install Git.Git & exit /b 1)
where node >nul 2>&1 || (echo ERRO: Node.js nao encontrado. Instale com: winget install OpenJS.NodeJS.LTS & exit /b 1)
if not exist "%SCRIPT%" (echo ERRO: nao achei %SCRIPT% & exit /b 1)

for /f %%i in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd')"') do set "HOJE=%%i"

if not exist "%REPO_DIR%\.git" (
  git clone -q "%REPO_URL%" "%REPO_DIR%" || (echo ERRO: nao consegui clonar %REPO_URL% & exit /b 1)
)
cd /d "%REPO_DIR%"
git fetch -q origin

git ls-remote --exit-code --heads origin %BRANCH% >nul 2>&1
if errorlevel 1 goto branch_nova
git checkout -q -B %BRANCH% origin/%BRANCH%
git reset -q --hard origin/%BRANCH%
goto gerar

:branch_nova
rem Branch ainda nao existe: comeca vazia, so com os relatorios.
git symbolic-ref HEAD refs/heads/%BRANCH%
git rm -r -q --cached . >nul 2>&1

:gerar
git config user.name >nul 2>&1 || git config user.name "Relatorio de uso do Claude Code"
git config user.email >nul 2>&1 || git config user.email "relatorio-tokens@users.noreply.github.com"

node "%SCRIPT%" --saida "%REPO_DIR%\relatorios\%COMPUTERNAME%" --dias %DIAS% --resumo-ia %RESUMO_IA% --ignorar-pasta "%BASE%" --pc "%COMPUTERNAME%"
if errorlevel 1 (echo ERRO: falha ao gerar o relatorio. & exit /b 1)

git add -A relatorios
git diff --cached --quiet && (echo Nada novo para enviar. & exit /b 0)
git commit -q -m "Relatorio de uso: %COMPUTERNAME% %HOJE%"

set /a TENTATIVA=0
:enviar
git push -q -u origin %BRANCH% && (echo Enviado para %REPO_URL% [%BRANCH%]. & exit /b 0)
set /a TENTATIVA+=1
if %TENTATIVA% geq 4 (echo ERRO: nao consegui enviar apos 4 tentativas. & exit /b 1)
echo Envio falhou, tentando de novo...
git pull -q --rebase origin %BRANCH%
ping -n 11 127.0.0.1 >nul
goto enviar
