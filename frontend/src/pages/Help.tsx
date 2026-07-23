import { Link } from 'react-router-dom'
import { Card } from '@/components/ui'
import { Icon, IconName } from '@/components/icons'

interface Feat { icon: IconName; title: string; desc: string; to?: string }
interface Section { icon: IconName; title: string; items: Feat[] }

const SECTIONS: Section[] = [
  {
    icon: 'dashboard', title: 'Operação',
    items: [
      { icon: 'dashboard', title: 'Dashboard', desc: 'KPIs, Security Score, tendências (sparklines) e falhas por hora. Exporta PDF com gráficos SVG.', to: '/' },
      { icon: 'health', title: 'Saúde do Ambiente', desc: 'Health checks estilo Ceph (OK/WARN/ERR) com donut e alertas.', to: '/health' },
      { icon: 'lock', title: 'Bloqueios', desc: 'Investigação de bloqueios de conta com origem e playbooks.', to: '/lockouts' },
      { icon: 'list', title: 'Eventos', desc: 'Eventos normalizados do AD/WEF com filtros e correlação.', to: '/events' },
      { icon: 'alert', title: 'Alertas', desc: 'Fila de alertas (inclui achados de scan) com dedup e triagem.', to: '/alerts' },
    ],
  },
  {
    icon: 'posture', title: 'Identidade & Active Directory',
    items: [
      { icon: 'posture', title: 'Postura de Segurança', desc: 'Score A–F, fatores de risco e distribuição (donut interativo). Exporta PDF.', to: '/posture' },
      { icon: 'users', title: 'Usuários', desc: 'Busca e detalhe de contas do AD (somente leitura).', to: '/search' },
      { icon: 'groups', title: 'Grupos', desc: 'Grupos privilegiados e membros.', to: '/groups' },
      { icon: 'computer', title: 'Computadores', desc: 'Inventário de máquinas com distribuição de SO e legado.', to: '/computers' },
      { icon: 'star', title: 'Watchlists', desc: 'Monitore entidades específicas.', to: '/watchlists' },
    ],
  },
  {
    icon: 'target', title: 'Segurança Ofensiva & Scan',
    items: [
      { icon: 'target', title: 'Superfície de Ataque', desc: 'Kerberoasting, AS-REP e contas administrativas de risco.', to: '/attack-surface' },
      { icon: 'target', title: 'Scan de Segurança (nmap)', desc: '12 perfis: rápido, serviços, exposição de AD, SMB, RDP, DNS, web, vuln SMB (MS17-010), discovery, full. Inspetor de TLS. Allowlist + RBAC + auditoria.', to: '/security-scan' },
    ],
  },
  {
    icon: 'list', title: 'Security Operations (Findings)',
    items: [
      { icon: 'dashboard', title: 'Visão Geral', desc: 'Postura consolidada: por severidade, categoria e ativo + fila “corrigir primeiro”.', to: '/security/overview' },
      { icon: 'alert', title: 'Vulnerabilidades', desc: 'CVEs de OS/dependências normalizados, com risco e links NVD/MITRE.', to: '/security/findings?category=vulnerability' },
      { icon: 'lock', title: 'Segredos expostos', desc: 'Segredos detectados — sempre mascarados, nunca exibidos crus.', to: '/security/findings?category=secret' },
      { icon: 'capacity', title: 'Contêineres', desc: 'Vulnerabilidades e misconfig de imagens Docker.', to: '/security/findings?asset_type=image' },
      { icon: 'settings', title: 'Misconfigurações & Hardening', desc: 'Dockerfile, config e hardening Linux (Lynis).', to: '/security/findings?category=misconfiguration' },
      { icon: 'download', title: 'Ingestão multi-scanner', desc: 'Importe Trivy, Grype, Gitleaks, npm audit, pip-audit e Lynis. Dedup automático + auditoria.', to: '/security/findings' },
    ],
  },
  {
    icon: 'megaphone', title: 'Comunicação & Integrações',
    items: [
      { icon: 'megaphone', title: 'Central de Mensagens', desc: 'Avisos a usuários filtrados (ex.: senha a expirar). RBAC + confirmação + auditoria.', to: '/message-center' },
      { icon: 'mail', title: 'Notificações', desc: 'Histórico de entregas (e-mail com identidade Astra).', to: '/notifications' },
      { icon: 'integrations', title: 'Integrações', desc: 'Google Chat, Teams/Slack/Discord, GLPI, webhooks.', to: '/integrations' },
    ],
  },
  {
    icon: 'settings', title: 'Sistema & Observabilidade',
    items: [
      { icon: 'report', title: 'Relatórios', desc: '12+ tipos (postura, superfície, contas, inventário de máquinas…). Export CSV/PDF.', to: '/reports' },
      { icon: 'capacity', title: 'Pontos de Coleta', desc: 'Atividade por Domain Controller, fontes e checkpoints de ingestão.', to: '/collection-points' },
      { icon: 'capacity', title: 'Capacidade & Manutenção', desc: 'Tamanho do banco, ingestão, limpeza e VACUUM FULL.', to: '/capacity' },
      { icon: 'user', title: 'Aparência (Tema)', desc: 'Temas Devils Never Cry (vermelho) e Bury the Light (azul). A interface inteira adapta.', to: '/account' },
      { icon: 'settings', title: 'Admin', desc: 'Diagnósticos e administração.', to: '/admin' },
    ],
  },
]

const FACE_ICONS: IconName[] = ['dashboard', 'target', 'lock', 'alert', 'posture', 'integrations']

export function Help() {
  return (
    <>
      <div className="hero">
        <div className="hero-scan" />
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Central de <span className="accent-text">Ajuda</span></h1>
            <div className="page-sub" style={{ marginTop: 4 }}>Tour por todas as funcionalidades da plataforma · somente leitura no AD</div>
          </div>
        </div>
      </div>

      {/* Hero 3D */}
      <div className="help-stage">
        <div className="help-cube">
          {FACE_ICONS.map((ic, i) => (
            <div key={i} className={`help-face f${i + 1}`}><Icon name={ic} size={34} /></div>
          ))}
        </div>
      </div>

      <div className="help-grid">
        {SECTIONS.map((s, si) => (
          <Card key={s.title} className="help-card">
            <div style={{ animationDelay: `${si * 60}ms` }}>
              <h3><Icon name={s.icon} size={18} /> {s.title}</h3>
              <div style={{ marginTop: 6 }}>
                {s.items.map((it) => (
                  <div className="help-item" key={it.title}>
                    <span className="hi-ic"><Icon name={it.icon} size={17} /></span>
                    <div style={{ flex: 1 }}>
                      <div className="hi-t">{it.title}</div>
                      <div className="hi-d">{it.desc}</div>
                      {it.to && <Link to={it.to}>Abrir →</Link>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="muted" style={{ fontSize: 11, marginTop: 16, textAlign: 'center' }}>
        Dica: pressione <kbd style={{ fontFamily: 'var(--mono)', border: '1px solid var(--border)', borderRadius: 4, padding: '1px 6px' }}>Ctrl</kbd> +{' '}
        <kbd style={{ fontFamily: 'var(--mono)', border: '1px solid var(--border)', borderRadius: 4, padding: '1px 6px' }}>K</kbd> para a busca global.
      </div>
    </>
  )
}
