#!/usr/bin/env node
// Relatório diário de uso do Claude Code neste computador.
//
// Lê os registros locais das sessões (~/.claude/projects/**/*.jsonl) e gera,
// para cada dia, um relatório em texto (.txt) com:
//   - tokens gastos (entrada, saída, cache criado, cache lido)
//   - modelo e nível de esforço usados
//   - por sessão: projeto, branch, pedidos feitos, arquivos alterados e commits do dia
//   - opcionalmente, um resumo simplificado do dia escrito pelo próprio Claude
//
// Uso: node relatorio-tokens.js --saida <pasta> [--dias 2] [--resumo-ia 1] [--ignorar-pasta <pasta>]
// Não tem dependências além do Node.js 18+.

'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

// ---------- argumentos ----------
const args = process.argv.slice(2);
function arg(nome, padrao) {
  const i = args.indexOf('--' + nome);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : padrao;
}
const SAIDA = arg('saida', path.join(process.cwd(), 'relatorios'));
const DIAS = Math.max(1, parseInt(arg('dias', '2'), 10) || 2);
const RESUMO_IA = arg('resumo-ia', '1') === '1';
const MODELO_RESUMO = arg('modelo-resumo', 'haiku');
const IGNORAR_PASTA = (arg('ignorar-pasta', '') || '').toLowerCase();
const PC = arg('pc', os.hostname());
// --excluir-hoje 1: só dias que já terminaram (para o relatório do dia anterior).
const EXCLUIR_HOJE = arg('excluir-hoje', '0') === '1';
// --so-faltantes 1: não refaz dias que já têm relatório completo.
const SO_FALTANTES = arg('so-faltantes', '0') === '1';
const CLAUDE_DIR = process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude');
const PROJETOS = path.join(CLAUDE_DIR, 'projects');

// ---------- utilidades ----------
function dataLocal(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
function horaLocal(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}
const fmt = (n) => Number(n || 0).toLocaleString('pt-BR');
const corta = (s, n) => {
  s = String(s || '').replace(/\s+/g, ' ').trim();
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
};

const HOJE = dataLocal(new Date());
const diasAlvo = new Set();
for (let i = EXCLUIR_HOJE ? 1 : 0; i < DIAS + (EXCLUIR_HOJE ? 1 : 0); i++) {
  const d = new Date();
  d.setDate(d.getDate() - i);
  diasAlvo.add(dataLocal(d));
}
const limiteMtime = Date.now() - (DIAS + 2) * 86400000;

function listarJsonl(dir, saida = []) {
  let itens;
  try { itens = fs.readdirSync(dir, { withFileTypes: true }); } catch { return saida; }
  for (const it of itens) {
    const p = path.join(dir, it.name);
    if (it.isDirectory()) listarJsonl(p, saida);
    else if (it.isFile() && it.name.endsWith('.jsonl')) {
      try { if (fs.statSync(p).mtimeMs >= limiteMtime) saida.push(p); } catch {}
    }
  }
  return saida;
}

function textoDoPedido(msg) {
  if (!msg) return '';
  const c = msg.content;
  if (typeof c === 'string') return c;
  if (Array.isArray(c)) {
    if (c.some((b) => b && b.type === 'tool_result')) return '';
    return c.filter((b) => b && b.type === 'text').map((b) => b.text).join(' ');
  }
  return '';
}

// ---------- leitura ----------
// sessoes: chave "dia|sessionId"
const sessoes = new Map();
const titulos = new Map(); // sessionId -> título
const mensagensVistas = new Map(); // "dia|sessionId|msgId" -> usage já contado

function sessao(dia, id) {
  const k = dia + '|' + id;
  if (!sessoes.has(k)) {
    sessoes.set(k, {
      dia, id, cwd: '', branch: '', inicio: null, fim: null,
      tokens: { entrada: 0, saida: 0, cacheCriado: 0, cacheLido: 0 },
      respostas: 0, modelos: {}, esforcos: {}, pedidos: [], arquivos: new Set(),
    });
  }
  return sessoes.get(k);
}

for (const arquivo of listarJsonl(PROJETOS)) {
  let conteudo;
  try { conteudo = fs.readFileSync(arquivo, 'utf8'); } catch { continue; }
  for (const linha of conteudo.split('\n')) {
    if (!linha.trim()) continue;
    let d;
    try { d = JSON.parse(linha); } catch { continue; }
    const id = d.sessionId;
    if (!id) continue;

    if (d.type === 'ai-title' && d.aiTitle) { titulos.set(id, d.aiTitle); continue; }
    if (d.type === 'summary' && d.summary && !titulos.has(id)) { titulos.set(id, d.summary); continue; }
    if (!d.timestamp) continue;

    const quando = new Date(d.timestamp);
    if (isNaN(quando)) continue;
    const dia = dataLocal(quando);
    if (!diasAlvo.has(dia)) continue;
    if (IGNORAR_PASTA && String(d.cwd || '').toLowerCase().startsWith(IGNORAR_PASTA)) continue;

    if (d.type !== 'assistant' && d.type !== 'user') continue;
    const s = sessao(dia, id);
    if (d.cwd && !d.isSidechain) s.cwd = d.cwd;
    if (d.gitBranch && !d.isSidechain) s.branch = d.gitBranch;
    if (!s.inicio || quando < s.inicio) s.inicio = quando;
    if (!s.fim || quando > s.fim) s.fim = quando;

    if (d.type === 'user') {
      if (d.isSidechain || d.isMeta || d.toolUseResult) continue;
      const t = textoDoPedido(d.message).trim();
      if (t && !t.startsWith('<') && !t.startsWith('[Request interrupted')) s.pedidos.push(t);
      continue;
    }

    // assistant
    const m = d.message || {};
    const u = m.usage;
    for (const b of Array.isArray(m.content) ? m.content : []) {
      if (b && b.type === 'tool_use' && b.input) {
        const alvo = b.input.file_path || b.input.notebook_path;
        if (alvo && /^(Edit|Write|MultiEdit|NotebookEdit)$/.test(b.name)) s.arquivos.add(alvo);
      }
    }
    if (!u || !m.id || m.model === '<synthetic>') continue;

    // A mesma resposta aparece em várias linhas (uma por bloco); conta só uma vez,
    // ficando com o maior valor de cada campo.
    const chave = dia + '|' + id + '|' + m.id;
    const atual = {
      entrada: u.input_tokens || 0,
      saida: u.output_tokens || 0,
      cacheCriado: u.cache_creation_input_tokens || 0,
      cacheLido: u.cache_read_input_tokens || 0,
    };
    const antes = mensagensVistas.get(chave);
    if (!antes) {
      s.respostas++;
      const modelo = m.model || 'desconhecido';
      const esforco = d.effort || 'não registrado';
      s.modelos[modelo] = (s.modelos[modelo] || 0) + 1;
      s.esforcos[esforco] = (s.esforcos[esforco] || 0) + 1;
      mensagensVistas.set(chave, { ...atual, modelo, esforco });
      for (const k in atual) s.tokens[k] += atual[k];
    } else {
      for (const k in atual) {
        if (atual[k] > antes[k]) { s.tokens[k] += atual[k] - antes[k]; antes[k] = atual[k]; }
      }
    }
  }
}

// Tokens por modelo e por esforço (a partir das respostas únicas).
function porChave(dia, campo) {
  const r = {};
  for (const [k, v] of mensagensVistas) {
    if (!k.startsWith(dia + '|')) continue;
    const nome = v[campo];
    r[nome] = r[nome] || { entrada: 0, saida: 0, cacheCriado: 0, cacheLido: 0, respostas: 0 };
    for (const t of ['entrada', 'saida', 'cacheCriado', 'cacheLido']) r[nome][t] += v[t];
    r[nome].respostas++;
  }
  return r;
}

// ---------- commits do dia ----------
const cacheRaiz = new Map();
function raizGit(cwd) {
  if (!cwd) return '';
  if (cacheRaiz.has(cwd)) return cacheRaiz.get(cwd);
  let raiz = '';
  if (fs.existsSync(cwd)) {
    const r = spawnSync('git', ['-C', cwd, 'rev-parse', '--show-toplevel'], { encoding: 'utf8' });
    if (r.status === 0) raiz = r.stdout.trim();
  }
  cacheRaiz.set(cwd, raiz);
  return raiz;
}
function commitsDoDia(raiz, dia) {
  if (!raiz) return [];
  const r = spawnSync('git', [
    '-C', raiz, 'log', '--all', '--no-merges',
    `--since=${dia} 00:00:00`, `--until=${dia} 23:59:59`,
    '--pretty=format:%h|%ad|%s', '--date=format:%H:%M',
  ], { encoding: 'utf8' });
  if (r.status !== 0 || !r.stdout.trim()) return [];
  return r.stdout.trim().split('\n').map((l) => {
    const [hash, hora, ...resto] = l.split('|');
    return { hash, hora, mensagem: resto.join('|') };
  });
}

// ---------- resumo pelo Claude ----------
function resumoIA(dados) {
  const entrada = [
    'Escreva em português do Brasil um resumo curto (no máximo 8 tópicos) do que foi feito',
    'neste dia de trabalho com o Claude Code, a partir dos dados abaixo. Agrupe por projeto,',
    'diga o que foi implementado ou corrigido em linguagem simples e não invente nada que não',
    'esteja nos dados. Responda só com os tópicos em texto simples, um por linha começando com "- ", sem Markdown e sem título.',
    '',
    JSON.stringify(dados.sessoes.map((s) => ({
      projeto: s.projeto, titulo: s.titulo, branch: s.branch,
      pedidos: s.pedidos.slice(0, 8).map((p) => corta(p, 300)),
      arquivos: s.arquivos.slice(0, 30), commits: s.commits.map((c) => c.mensagem),
    })), null, 1),
  ].join('\n');
  const r = spawnSync('claude', ['-p', '--model', MODELO_RESUMO, '--max-turns', '1'], {
    input: entrada, encoding: 'utf8', shell: process.platform === 'win32', timeout: 180000,
    cwd: IGNORAR_PASTA ? arg('ignorar-pasta') : os.tmpdir(),
  });
  if (r.status === 0 && r.stdout.trim()) return r.stdout.trim();
  return null;
}

// ---------- montagem ----------
function nomeProjeto(cwd, raiz) {
  return path.basename(raiz || cwd || '') || '(sem pasta)';
}

const gerados = [];
function relatorioCompleto(dia) {
  try {
    const j = JSON.parse(fs.readFileSync(path.join(SAIDA, dia.slice(0, 7), '.dados', dia + '.json'), 'utf8'));
    return j.completo === true;
  } catch { return false; }
}

const pulados = [];
for (const dia of [...diasAlvo].sort()) {
  if (SO_FALTANTES && relatorioCompleto(dia)) { pulados.push(dia); continue; }
  const lista = [...sessoes.values()].filter((s) => s.dia === dia && (s.respostas > 0 || s.pedidos.length));
  if (!lista.length) continue;

  const raizesVistas = new Set();
  const sessoesDia = lista.sort((a, b) => a.inicio - b.inicio).map((s) => {
    const raiz = raizGit(s.cwd);
    // Commits aparecem só na primeira sessão de cada repositório, para não repetir.
    const commits = raiz && !raizesVistas.has(raiz) ? commitsDoDia(raiz, dia) : [];
    if (raiz) raizesVistas.add(raiz);
    const base = raiz || s.cwd;
    return {
      id: s.id,
      titulo: titulos.get(s.id) || corta(s.pedidos[0] || '(sem título)', 80),
      projeto: nomeProjeto(s.cwd, raiz),
      pasta: s.cwd, branch: s.branch,
      inicio: s.inicio ? horaLocal(s.inicio) : '', fim: s.fim ? horaLocal(s.fim) : '',
      respostas: s.respostas, tokens: s.tokens,
      total: s.tokens.entrada + s.tokens.saida + s.tokens.cacheCriado + s.tokens.cacheLido,
      modelos: s.modelos, esforcos: s.esforcos,
      pedidos: s.pedidos,
      arquivos: [...s.arquivos].map((a) => (base && a.toLowerCase().startsWith(base.toLowerCase())
        ? path.relative(base, a) : a).replace(/\\/g, '/')).sort(),
      commits,
    };
  });

  const totais = { entrada: 0, saida: 0, cacheCriado: 0, cacheLido: 0 };
  for (const s of sessoesDia) for (const k in totais) totais[k] += s.tokens[k];
  const dados = {
    computador: PC, dia, geradoEm: new Date().toISOString(),
    completo: dia < HOJE, // falso quando o dia ainda está em andamento
    totais, total: totais.entrada + totais.saida + totais.cacheCriado + totais.cacheLido,
    porModelo: porChave(dia, 'modelo'), porEsforco: porChave(dia, 'esforco'),
    sessoes: sessoesDia,
  };

  const pastaMes = path.join(SAIDA, dia.slice(0, 7));
  fs.mkdirSync(pastaMes, { recursive: true });
  // Dados brutos ficam numa subpasta, só para reaproveitar o resumo na próxima execução.
  const pastaDados = path.join(pastaMes, '.dados');
  fs.mkdirSync(pastaDados, { recursive: true });
  const arqJson = path.join(pastaDados, dia + '.json');
  const arqTxt = path.join(pastaMes, dia + '.txt');

  // Reaproveita o resumo anterior se os dados do dia não mudaram (evita gastar tokens à toa).
  let resumo = null;
  const assinatura = JSON.stringify(sessoesDia.map((s) => [s.id, s.respostas, s.pedidos.length, s.arquivos.length, s.commits.length]));
  try {
    const anterior = JSON.parse(fs.readFileSync(arqJson, 'utf8'));
    if (anterior.assinatura === assinatura && anterior.resumo) resumo = anterior.resumo;
  } catch {}
  if (!resumo && RESUMO_IA) resumo = resumoIA(dados);
  dados.assinatura = assinatura;
  dados.resumo = resumo;

  fs.writeFileSync(arqJson, JSON.stringify(dados, null, 2) + '\n');
  // BOM no início para o Bloco de Notas abrir os acentos corretamente.
  fs.writeFileSync(arqTxt, '\ufeff' + texto(dados).replace(/\n/g, '\r\n'));
  gerados.push(arqTxt);
}

function listaContagem(obj) {
  return Object.entries(obj).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} (${v})`).join(', ') || '-';
}
function colunas(nome, t) {
  const c = (v, n) => fmt(v).padStart(n);
  return `${nome.padEnd(26)}${c(t.entrada, 12)}${c(t.saida, 12)}${c(t.cacheCriado, 15)}${c(t.cacheLido, 16)}`;
}
function titulo(s, ch) { return s + '\n' + ch.repeat(Math.min(s.length, 78)); }

function texto(d) {
  const L = [];
  L.push(titulo(`USO DO CLAUDE CODE - ${d.computador} - ${d.dia}`, '='), '');
  L.push(`${d.sessoes.length} sessao(oes), ${fmt(d.total)} tokens no total.`, '');

  L.push(titulo('O QUE FOI FEITO', '-'));
  if (d.resumo) L.push(d.resumo.replace(/\*\*/g, ''));
  else for (const s of d.sessoes) {
    const c = s.commits.length ? `; commits: ${s.commits.map((x) => x.mensagem).join('; ')}` : '';
    L.push(`- ${s.projeto}: ${s.titulo} (${s.arquivos.length} arquivo(s) alterado(s)${c})`);
  }
  L.push('');

  L.push(titulo('TOKENS DO DIA', '-'));
  L.push(`${''.padEnd(26)}${'Entrada'.padStart(12)}${'Saida'.padStart(12)}${'Cache criado'.padStart(15)}${'Cache lido'.padStart(16)}`);
  L.push(colunas('TOTAL', d.totais));
  for (const [m, t] of Object.entries(d.porModelo)) L.push(colunas(m, t));
  L.push('');
  L.push('Por esforco:');
  for (const [e, t] of Object.entries(d.porEsforco)) L.push(`  ${e}: ${fmt(t.respostas)} respostas, ${fmt(t.saida)} tokens de saida`);
  L.push('');

  L.push(titulo('SESSOES', '-'), '');
  for (const s of d.sessoes) {
    L.push(`> ${s.titulo}`);
    L.push(`  Projeto:  ${s.projeto}${s.branch ? ` (branch ${s.branch})` : ''}`);
    L.push(`  Horario:  ${s.inicio} - ${s.fim}, ${s.respostas} respostas`);
    L.push(`  Modelo:   ${listaContagem(s.modelos)}`);
    L.push(`  Esforco:  ${listaContagem(s.esforcos)}`);
    L.push(`  Tokens:   ${fmt(s.total)} (entrada ${fmt(s.tokens.entrada)}, saida ${fmt(s.tokens.saida)}, cache criado ${fmt(s.tokens.cacheCriado)}, cache lido ${fmt(s.tokens.cacheLido)})`);
    if (s.pedidos.length) {
      L.push('  Pedidos:');
      for (const p of s.pedidos.slice(0, 5)) L.push(`    - ${corta(p, 160)}`);
      if (s.pedidos.length > 5) L.push(`    - ... e mais ${s.pedidos.length - 5}`);
    }
    if (s.arquivos.length) {
      L.push(`  Arquivos alterados (${s.arquivos.length}):`);
      for (const a of s.arquivos.slice(0, 15)) L.push(`    - ${a}`);
      if (s.arquivos.length > 15) L.push('    - ...');
    }
    if (s.commits.length) {
      L.push('  Commits do dia no repositorio:');
      for (const c of s.commits) L.push(`    - ${c.hash} ${c.hora} ${corta(c.mensagem, 120)}`);
    }
    L.push('');
  }
  L.push(`Gerado em ${new Date(d.geradoEm).toLocaleString('pt-BR')} a partir dos registros locais do Claude Code.` +
    (d.completo ? '' : ' Parcial: o dia ainda estava em andamento.'), '');
  return L.join('\n');
}

if (gerados.length) console.log('Relatórios gerados:\n' + gerados.join('\n'));
if (pulados.length) console.log(`Já tinham relatório completo: ${pulados.join(', ')}`);
if (!gerados.length && !pulados.length) console.log(`Nenhuma sessão encontrada em ${PROJETOS} no período.`);
