import { useEffect, useRef, useState } from 'react'
import type { MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui'
import { Icon, IconName } from '@/components/icons'

const TOUR_MS = 5200

interface Mod {
  id: string
  icon: IconName
  sats: IconName[]      // ícones que orbitam na animação 3D
  title: string
  tagline: string
  points: string[]
  to: string
}

const MODULES: Mod[] = [
  {
    id: 'dashboard', icon: 'dashboard', sats: ['alert', 'lock', 'posture', 'list'],
    title: 'Dashboard', tagline: 'Centro de Operações de Identidade',
    points: [
      'KPIs ao vivo: bloqueios, falhas de auth, alertas críticos, contas privilegiadas.',
      'Security Score com tendência e sparklines de 14 dias.',
      'Falhas de autenticação por hora e rankings.',
      'Exporta relatório em PDF com gráficos SVG (donut + sparklines).',
    ], to: '/',
  },
  {
    id: 'health', icon: 'health', sats: ['check', 'alert', 'bell', 'dot'],
    title: 'Saúde do Ambiente', tagline: 'Health checks estilo Ceph',
    points: [
      'Status geral OK / WARN / ERR com donut de distribuição.',
      'Checks com severidade, detalhe e link para investigar.',
      'Alimenta o sino e os alertas automáticos do Google Chat.',
    ], to: '/health',
  },
  {
    id: 'lockouts', icon: 'lock', sats: ['users', 'computer', 'list', 'target'],
    title: 'Bloqueios de Conta', tagline: 'Investigação com origem e playbooks',
    points: [
      'Origem do bloqueio correlacionada (DC, computador, IP).',
      'Playbooks guiados de investigação.',
      'Histórico e recorrência por conta.',
    ], to: '/lockouts',
  },
  {
    id: 'posture', icon: 'posture', sats: ['star', 'lock', 'users', 'alert'],
    title: 'Postura de Segurança', tagline: 'Score A–F e distribuição de risco',
    points: [
      'Security Score com gauge e fatores de risco.',
      'Donut interativo de distribuição por categoria.',
      'Explorador de categorias com drill-down por conta.',
      'Exporta PDF com pizza e tabela de fatores.',
    ], to: '/posture',
  },
  {
    id: 'attack', icon: 'target', sats: ['lock', 'users', 'star', 'alert'],
    title: 'Superfície de Ataque', tagline: 'Kerberoasting, AS-REP e admins de risco',
    points: [
      'Detecções explicáveis com risco, evidências e MITRE.',
      'Contas com SPN, sem pré-auth e administrativas obsoletas.',
    ], to: '/attack-surface',
  },
  {
    id: 'scan', icon: 'target', sats: ['lock', 'computer', 'integrations', 'refresh'],
    title: 'Scan de Segurança (nmap)', tagline: '12 perfis + inspetor de TLS',
    points: [
      'Rápido, serviços, exposição de AD, SMB, RDP, DNS, web, vuln SMB (MS17-010), discovery, full.',
      'Inspetor de certificado/TLS (validade, protocolo fraco, auto-assinado).',
      'Allowlist de alvos + RBAC + confirmação + auditoria.',
      'Achados viram alertas e findings normalizados; exporta relatório.',
    ], to: '/security-scan',
  },
  {
    id: 'secops', icon: 'list', sats: ['alert', 'lock', 'capacity', 'download'],
    title: 'Security Operations', tagline: 'Central de findings multi-scanner',
    points: [
      'Ingestão de Trivy, Grype, Gitleaks, npm audit, pip-audit e Lynis.',
      'Modelo normalizado, dedup por fingerprint e risco por contexto.',
      'Vulnerabilidades, segredos (mascarados), contêineres, misconfig e hardening.',
      'Supressão com motivo/expiração e estado de remediação — tudo auditado.',
    ], to: '/security/overview',
  },
  {
    id: 'inventory', icon: 'users', sats: ['groups', 'computer', 'star', 'search'],
    title: 'Inventário de Identidades', tagline: 'Usuários, grupos e máquinas',
    points: [
      'Busca e detalhe de contas do AD (somente leitura).',
      'Grupos privilegiados e membros; computadores com SO/legado.',
      'Watchlists para monitorar entidades específicas.',
    ], to: '/search',
  },
  {
    id: 'comms', icon: 'megaphone', sats: ['mail', 'integrations', 'send', 'bell'],
    title: 'Comunicação & Integrações', tagline: 'Avisos e ChatOps',
    points: [
      'Central de Mensagens com filtro de contas (RBAC + confirmação + auditoria).',
      'E-mail com identidade Astra; Google Chat, Teams/Slack/Discord, GLPI.',
      'Histórico de notificações e entregas.',
    ], to: '/message-center',
  },
  {
    id: 'reports', icon: 'report', sats: ['download', 'posture', 'list', 'computer'],
    title: 'Relatórios & Exportação', tagline: '12+ tipos, CSV e PDF',
    points: [
      'Postura, superfície de ataque, contas de serviço, inventário de máquinas…',
      'Exportação de Dashboard/Postura em PDF com gráficos SVG.',
    ], to: '/reports',
  },
  {
    id: 'collection', icon: 'capacity', sats: ['computer', 'refresh', 'alert', 'integrations'],
    title: 'Pontos de Coleta', tagline: 'Ingestão por Domain Controller',
    points: [
      'Atividade por DC (24h/7d), status ativo/ocioso/parado.',
      'Fontes/conectores e checkpoints reais de coleta.',
    ], to: '/collection-points',
  },
  {
    id: 'system', icon: 'settings', sats: ['capacity', 'trash', 'zap', 'user'],
    title: 'Capacidade, Manutenção & Tema', tagline: 'Observabilidade e aparência',
    points: [
      'Tamanho do banco, taxa de ingestão, limpeza e VACUUM FULL.',
      'Temas Devils Never Cry (vermelho) e Bury the Light (azul) — a interface inteira adapta.',
    ], to: '/capacity',
  },
]

export function Help() {
  const [active, setActive] = useState(MODULES[0].id)
  const [tour, setTour] = useState(false)
  const sceneRef = useRef<HTMLDivElement>(null)
  const m = MODULES.find((x) => x.id === active) || MODULES[0]

  // Tour guiado: avança automaticamente pelos módulos, em loop.
  useEffect(() => {
    if (!tour) return
    const t = setInterval(() => {
      setActive((cur) => {
        const i = MODULES.findIndex((x) => x.id === cur)
        return MODULES[(i + 1) % MODULES.length].id
      })
    }, TOUR_MS)
    return () => clearInterval(t)
  }, [tour])

  // Parallax/tilt reagindo ao mouse (via ref, sem re-render).
  function onMove(e: MouseEvent<HTMLDivElement>) {
    const el = sceneRef.current
    if (!el) return
    const r = e.currentTarget.getBoundingClientRect()
    const x = (e.clientX - r.left) / r.width - 0.5
    const y = (e.clientY - r.top) / r.height - 0.5
    el.style.transform = `rotateX(${(-y * 22).toFixed(1)}deg) rotateY(${(x * 30).toFixed(1)}deg)`
  }
  function onLeave() {
    if (sceneRef.current) sceneRef.current.style.transform = 'rotateX(0deg) rotateY(0deg)'
  }
  function pick(id: string) { setTour(false); setActive(id) }

  return (
    <>
      <div className="hero">
        <div className="hero-scan" />
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Central de <span className="accent-text">Ajuda</span> & Tour</h1>
            <div className="page-sub" style={{ marginTop: 4 }}>Escolha um módulo → explicação animada 3D → vá direto para ele · mova o mouse na cena</div>
          </div>
          <button className="btn-icon" onClick={() => setTour((v) => !v)} title="Percorre os módulos automaticamente">
            <Icon name={tour ? 'pause' : 'play'} size={15} /> {tour ? 'Pausar tour' : 'Tour guiado'}
          </button>
        </div>
      </div>

      <div className="faq-shell">
        <div className="faq-list">
          {MODULES.map((mod) => (
            <button key={mod.id} className={`faq-tab ${mod.id === active ? 'active' : ''}`} onClick={() => pick(mod.id)}>
              <Icon name={mod.icon} size={18} />
              <span>{mod.title}</span>
            </button>
          ))}
        </div>

        <Card>
          {/* key força reinício das animações ao trocar de módulo */}
          <div className="faq-panel" key={m.id}>
            {tour && (
              <div className="faq-progress"><i style={{ animation: `faq-prog ${TOUR_MS}ms linear` }} /></div>
            )}
            <div className="faq-stage" onMouseMove={onMove} onMouseLeave={onLeave}>
              <div className="faq-3d" ref={sceneRef}>
                <div className="faq-orbit">
                  {m.sats.map((s, i) => (
                    <span key={i} className={`faq-sat s${i}`}><Icon name={s} size={20} /></span>
                  ))}
                </div>
                <div className="faq-core"><Icon name={m.icon} size={44} /></div>
              </div>
            </div>

            <div className="faq-title">{m.title}</div>
            <div className="faq-tagline">{m.tagline}</div>
            <ul className="faq-points">
              {m.points.map((p, i) => (
                <li key={i} style={{ animationDelay: `${i * 70}ms` }}>
                  <Icon name="check" size={16} /><span>{p}</span>
                </li>
              ))}
            </ul>
            <Link to={m.to} className="btn-icon" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '10px 20px', borderRadius: 'var(--radius)', color: '#fff', textDecoration: 'none', fontWeight: 600, fontSize: 13, background: 'var(--grad-red)', boxShadow: '0 4px 16px var(--shadow-glow)' }}>
              <Icon name="external" size={15} /> Ir para o módulo
            </Link>
          </div>
        </Card>
      </div>

      <div className="muted" style={{ fontSize: 11, marginTop: 16, textAlign: 'center' }}>
        Dica: <kbd style={{ fontFamily: 'var(--mono)', border: '1px solid var(--border)', borderRadius: 4, padding: '1px 6px' }}>Ctrl</kbd> +{' '}
        <kbd style={{ fontFamily: 'var(--mono)', border: '1px solid var(--border)', borderRadius: 4, padding: '1px 6px' }}>K</kbd> abre a busca global · somente leitura no AD.
      </div>
    </>
  )
}
