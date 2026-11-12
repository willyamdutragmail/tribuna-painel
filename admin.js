(() => {
  const cfg = window.TRIBUNA_CONFIG || {};
  const app = document.getElementById('app');
  if (!cfg.url || !cfg.key) {
    app.innerHTML = '<div class="msg">Configuração ausente. Rode <b>npm run admin:web</b> na pasta do projeto.</div>';
    return;
  }
  const sb = window.supabase.createClient(cfg.url, cfg.key);
  const KIND = { student: 'Estudante de jornalismo', journalist: 'Jornalista' };
  const STATUS = { approved: 'Aprovada', rejected: 'Recusada', pending: 'Pendente' };
  let tab = 'review';

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '—');
  const fmtCpf = (c) => (c ? c.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, '$1.$2.$3-$4') : '—');
  const fmtPhone = (p) => (!p ? '—' : p.length === 11 ? p.replace(/^(\d{2})(\d{5})(\d{4})$/, '($1) $2-$3') : p.replace(/^(\d{2})(\d{4})(\d{4})$/, '($1) $2-$3'));
  const age = (iso) => {
    if (!iso) return '';
    const [y, m, d] = iso.split('-').map(Number); const n = new Date();
    let a = n.getFullYear() - y; if (n.getMonth() + 1 < m || (n.getMonth() + 1 === m && n.getDate() < d)) a--; return a;
  };
  const safeUrl = (u) => (/^https?:\/\//i.test(u || '') ? u : null);

  async function start() {
    const { data } = await sb.auth.getSession();
    if (!data.session) return renderLogin();
    const { data: me } = await sb.from('profiles').select('full_name, role, status').eq('id', data.session.user.id).maybeSingle();
    document.getElementById('who').textContent = data.session.user.email;
    document.getElementById('logout').hidden = false;
    if (!me || me.status !== 'active' || !['editor', 'admin'].includes(me.role)) {
      app.innerHTML = '<div class="msg">Esta conta não tem acesso ao painel. Só editores e administradores avaliam candidaturas.</div>';
      return;
    }
    const { data: aal } = await sb.auth.mfa.getAuthenticatorAssuranceLevel();
    if (aal?.currentLevel !== 'aal2') return renderMfa();
    renderList();
  }

  // ---------------------------------------------------------------- verificação em duas etapas (TOTP)
  async function renderMfa(error) {
    const { data, error: listErr } = await sb.auth.mfa.listFactors();
    if (listErr) return (app.innerHTML = `<div class="msg">Erro: ${esc(listErr.message)}</div>`);
    const factor = (data.totp || []).find((f) => f.status === 'verified');
    if (factor) return renderCode(factor.id, null, error);

    // Primeiro acesso: remove cadastros incompletos e cria um novo, com QR code.
    for (const f of data.all || []) if (f.status !== 'verified') await sb.auth.mfa.unenroll({ factorId: f.id });
    const { data: enr, error: enrErr } = await sb.auth.mfa.enroll({
      factorType: 'totp',
      friendlyName: `Painel TribunaOnline.org ${new Date().toISOString().slice(0, 16)}`,
    });
    if (enrErr) return (app.innerHTML = `<div class="msg">Não foi possível iniciar a verificação em duas etapas: ${esc(enrErr.message)}</div>`);
    renderCode(enr.id, enr.totp, error);
  }

  function renderCode(factorId, totp, error) {
    const qr = totp && /^data:image\/svg\+xml/.test(totp.qr_code) ? totp.qr_code : null;
    app.innerHTML = `
      <form class="login" id="mfa">
        <h2 style="margin:0 0 6px">Verificação em duas etapas</h2>
        ${totp ? `
          <div class="muted">Primeiro acesso: abra um aplicativo autenticador no celular (Google Authenticator,
            Microsoft Authenticator ou similar), toque em adicionar conta e leia o QR code.</div>
          ${qr ? `<img alt="QR code para o aplicativo autenticador" src="${esc(qr)}" style="display:block;width:200px;height:200px;margin:14px auto;background:#fff;border-radius:8px;padding:8px">` : ''}
          <div class="muted" style="font-size:13px">Sem câmera? Digite esta chave no aplicativo:<br><code style="word-break:break-all">${esc(totp.secret)}</code></div>`
        : `<div class="muted">Digite o código de 6 dígitos que aparece no seu aplicativo autenticador.</div>`}
        ${error ? `<div class="msg" style="margin-top:12px">${esc(error)}</div>` : ''}
        <label for="code">Código</label>
        <input id="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" required>
        <div style="margin-top:16px"><button class="primary" style="width:100%">Confirmar</button></div>
      </form>`;
    document.getElementById('code').focus();
    document.getElementById('mfa').onsubmit = async (e) => {
      e.preventDefault();
      const code = document.getElementById('code').value.replace(/\D/g, '');
      const { error: err } = await sb.auth.mfa.challengeAndVerify({ factorId, code });
      if (err) {
        if (totp) {
          // Mantém o mesmo QR code no primeiro acesso.
          return renderCode(factorId, totp, 'Código incorreto. Confira o horário do celular e tente de novo.');
        }
        return renderCode(factorId, null, 'Código incorreto ou expirado. Tente de novo.');
      }
      start();
    };
  }

  function renderLogin(error) {
    document.getElementById('who').textContent = '';
    document.getElementById('logout').hidden = true;
    app.innerHTML = `
      <form class="login" id="login">
        <h2 style="margin:0 0 6px">Entrar</h2>
        <div class="muted">Use a conta de editor ou administrador do app.</div>
        ${error ? `<div class="msg" style="margin-top:12px">${esc(error)}</div>` : ''}
        <label for="em">E-mail</label><input id="em" type="email" autocomplete="username" required>
        <label for="pw">Senha</label><input id="pw" type="password" autocomplete="current-password" required>
        <div style="margin-top:16px"><button class="primary" style="width:100%">Entrar</button></div>
      </form>`;
    document.getElementById('login').onsubmit = async (e) => {
      e.preventDefault();
      const email = document.getElementById('em').value.trim();
      const password = document.getElementById('pw').value;
      const { error: err } = await sb.auth.signInWithPassword({ email, password });
      if (err) return renderLogin('E-mail ou senha incorretos.');
      start();
    };
  }

  async function renderList(notice) {
    let q = sb.from('contributor_applications')
      .select('id, status, kind, institution, professional_registry, portfolio_url, motivation, full_name, cpf, birth_date, phone, city, state, email, email_confirmed_at, review_note, reviewed_at, created_at, user_id')
      .order('created_at', { ascending: tab !== 'done' }).limit(100);
    if (tab === 'review') q = q.eq('status', 'pending').not('email_confirmed_at', 'is', null);
    if (tab === 'email') q = q.eq('status', 'pending').is('email_confirmed_at', null);
    if (tab === 'done') q = q.neq('status', 'pending');
    const [{ data, error }, counts] = await Promise.all([q, countPending()]);

    const tabBtn = (k, label) => `<button data-tab="${k}" aria-pressed="${tab === k}">${label}</button>`;
    app.innerHTML = `
      ${notice ? `<div class="msg">${esc(notice)}</div>` : ''}
      <div class="tabs">
        ${tabBtn('review', `Para analisar (${counts.review})`)}
        ${tabBtn('email', `Aguardando e-mail (${counts.email})`)}
        ${tabBtn('done', 'Decididas')}
        <button id="reload" style="margin-left:auto">Atualizar</button>
      </div>
      ${error ? `<div class="msg">Erro: ${esc(error.message)}</div>` : ''}
      ${data && data.length ? data.map(card).join('') : `<div class="empty">Nenhuma candidatura aqui.</div>`}`;
    app.querySelectorAll('[data-tab]').forEach((b) => (b.onclick = () => { tab = b.dataset.tab; renderList(); }));
    document.getElementById('reload').onclick = () => renderList();
    app.querySelectorAll('[data-decide]').forEach((b) => (b.onclick = () => decide(Number(b.dataset.id), b.dataset.decide === 'approve')));
  }

  async function countPending() {
    const base = () => sb.from('contributor_applications').select('id', { count: 'exact', head: true }).eq('status', 'pending');
    const [a, b] = await Promise.all([base().not('email_confirmed_at', 'is', null), base().is('email_confirmed_at', null)]);
    return { review: a.count ?? 0, email: b.count ?? 0 };
  }

  function card(a) {
    const url = safeUrl(a.portfolio_url);
    const field = (label, value) => `<div><span>${label}</span>${value}</div>`;
    return `
      <article class="card">
        <h2>${esc(a.full_name || '(sem nome — candidatura antiga)')}
          <span class="chip">${esc(KIND[a.kind] || a.kind)}</span>
          ${a.status !== 'pending' ? `<span class="chip">${STATUS[a.status]}</span>` : ''}</h2>
        <div class="muted">Enviada em ${fmtDate(a.created_at)}${a.email_confirmed_at ? ` · e-mail confirmado em ${fmtDate(a.email_confirmed_at)}` : ' · e-mail ainda não confirmado'}</div>
        <div class="grid">
          ${field('CPF', esc(fmtCpf(a.cpf)))}
          ${field('Nascimento', a.birth_date ? `${esc(a.birth_date.split('-').reverse().join('/'))} (${age(a.birth_date)} anos)` : '—')}
          ${field('Celular', esc(fmtPhone(a.phone)))}
          ${field('E-mail', esc(a.email || '—'))}
          ${field('Cidade', esc([a.city, a.state].filter(Boolean).join(' / ') || '—'))}
          ${field(a.kind === 'student' ? 'Faculdade' : 'Veículo / atuação', esc(a.institution))}
          ${field('Registro MTb', esc(a.professional_registry || '—'))}
          ${field('Portfólio', url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(url)}</a>` : '—')}
        </div>
        ${a.motivation ? `<div><span class="muted">Motivação:</span> ${esc(a.motivation)}</div>` : ''}
        ${a.status === 'pending' && a.email_confirmed_at ? `
          <div class="actions">
            <textarea id="note-${a.id}" placeholder="Mensagem ao candidato (obrigatória para recusar)" maxlength="500"></textarea>
            <button class="ok" data-decide="approve" data-id="${a.id}">Aprovar</button>
            <button class="bad" data-decide="reject" data-id="${a.id}">Recusar</button>
          </div>` : ''}
        ${a.status !== 'pending' ? `<div class="muted">Decidida em ${fmtDate(a.reviewed_at)}${a.review_note ? ` · “${esc(a.review_note)}”` : ''}</div>` : ''}
      </article>`;
  }

  async function decide(id, approve) {
    const note = (document.getElementById(`note-${id}`)?.value || '').trim();
    if (!approve && note.length < 3) return alert('Escreva o motivo da recusa: o candidato verá essa mensagem no app.');
    if (!confirm(approve ? 'Aprovar esta candidatura? A pessoa passa a poder publicar.' : 'Recusar esta candidatura?')) return;
    app.querySelectorAll('button[data-decide]').forEach((b) => (b.disabled = true));
    const { error } = await sb.rpc('review_application', { p_application_id: id, p_approve: approve, p_note: note || null });
    renderList(error ? `Não foi possível concluir: ${error.message}` : approve ? 'Candidatura aprovada.' : 'Candidatura recusada.');
  }

  document.getElementById('logout').onclick = async () => { await sb.auth.signOut(); renderLogin(); };
  start();
})();
