# AXIS — Unified Operations Platform
### Product Blueprint & Commercial Architecture (v1.0)

> Working product name: **AXIS** (white-label ready). A multi-tenant B2B SaaS that
> unifies enterprise operations — procurement, repairs, assets, requests, approvals,
> endpoints, compliance, automation, and analytics — into a single command center.
>
> **Strategic premise:** the existing platform (AD/security operations, RBAC, audit
> spine, normalized findings, Celery/Redis/Postgres core) is not thrown away — it
> becomes the **Security & Endpoint Posture** pillar of AXIS. We monetize the hard,
> already-built parts (identity, audit, security posture) and grow outward into the
> high-volume operational modules that sell seats.

---

## 0. Relationship to the current codebase (reuse map)

| Already built (AD Audit Portal) | Becomes in AXIS |
|---|---|
| FastAPI + SQLModel + async psycopg | Core API runtime (unchanged) |
| React/TS + Vite + TanStack Query + code-splitting | App shell / design system base |
| RBAC by capability, LDAP/AD auth, MFA/TOTP | Identity & Access foundation → extend to multi-tenant scopes |
| `internal_audit_log` + `record_audit` | Enterprise Audit & Activity Center |
| Normalized **findings** model + adapters (Trivy/Grype/Gitleaks/Lynis…) | Compliance & Vulnerability pillar (premium) |
| nmap/TLS scan module, collection points, health checks | Device/Host & Endpoint Posture module |
| Redis (cache/lock/rate-limit), Celery worker/beat | Job engine for workflows, SLA timers, notifications |
| Alembic migrations, Docker Compose, hardening overrides | Deployment & tenancy substrate |

**Net effect:** ~40% of the "enterprise-grade plumbing" (auth, audit, jobs, security)
already exists. AXIS is an *expansion*, not a rewrite.

---

## 1. Product Vision

AXIS is a **unified operations command center** for mid-market and enterprise
organizations that run mixed Windows + Linux environments. It replaces the sprawl of
spreadsheets, email approvals, disconnected ticketing, and siloed asset tools with one
interconnected platform where **a request, its approval, the purchase, the asset it
creates, the device it becomes, its repairs, its contract, and its compliance state are
one continuous, auditable thread**.

Core beliefs:
- **Everything is an object with a lifecycle and an audit trail.** A laptop is an
  Asset → linked to a Purchase → an Approval → a Contract/Warranty → a Device (host) →
  Repairs → Compliance policies → eventual retirement. AXIS makes that graph first-class.
- **Operations are workflows, not forms.** Every module ships with a rule/workflow
  engine so customers encode *their* process without code.
- **Decisions need context and speed.** Dashboards, saved views, command palette, and
  an AI copilot compress time-to-decision.
- **Trust is the product.** Multi-tenant isolation, immutable-style audit, RBAC scopes,
  and least privilege are non-negotiable and are a *paid* differentiator.

**One-line pitch:** *"Run every operational request, asset, device, and approval in one
auditable, automated, AI-assisted platform — across Windows and Linux."*

---

## 2. Marketable Positioning

**Category:** Enterprise Operations & Service Management (ITSM-adjacent + Asset/Endpoint
+ Procurement + GRC-lite), delivered as multi-tenant SaaS.

**Who we sell to:**
- **IT / Infra Ops** (assets, devices, patch, repairs, endpoint posture)
- **Procurement / Finance Ops** (purchases, approvals, budgets, vendors, contracts)
- **Facilities / Maintenance** (repairs, spare parts, service providers, SLAs)
- **Security / Compliance** (policy center, audit, vulnerability posture) — *upsell*
- **Executives** (analytics, scorecards, exception reports)

**Differentiators vs. the field:**
- vs. generic ITSM (ServiceNow-heavy, Jira SM): faster to deploy, **asset↔purchase↔repair
  graph out-of-the-box**, Linux-first endpoint posture, dramatically lower TCO.
- vs. procurement-only tools: full **maintenance + asset lifecycle** in the same ledger.
- vs. endpoint MDM (Intune-style): we don't replace MDM; we **operationalize** it —
  approvals, requests, repairs, compliance evidence, and the human workflow around
  devices, with connectors to the real MDM/AD.
- vs. spreadsheets/email: an audit-grade, automated, multi-tenant system of record.

**Wedge:** land with **Purchases + Approvals + Assets** (immediate ROI, visible to
finance), expand into **Repairs + Devices + Compliance + Automation** (stickiness),
upsell **Security Posture + AI Copilot + Advanced Analytics** (margin).

---

## 3. Module Map

```
                          ┌──────────────────────────────────────────┐
                          │              AXIS PLATFORM               │
                          │  (multi-tenant · RBAC scopes · audit)    │
                          └──────────────────────────────────────────┘
  OPERATIONS CORE            LIFECYCLE & SUPPLY           ENDPOINT & SECURITY
  ─────────────────          ───────────────────           ────────────────────
  01 Requests/Catalog        03 Assets/Inventory           09 Devices/Hosts
  02 Approvals Center        06 Vendors/Suppliers          10 Software/Packages
  04 Purchases (Procure)     07 Contracts/Warranty         11 Patch/Update
  05 Repairs (Maint.)        08 Stock/Warehouse            12 Compliance/Policy
                                                            (S) Security Posture*
  PLATFORM SERVICES          INTELLIGENCE                  ADMIN & SAAS
  ─────────────────          ───────────────                ────────────────
  13 Automation/Workflows    16 Reports/Analytics          19 Identity/RBAC/Scopes
  14 Notifications Hub       17 Audit/Activity             20 API/Integrations/Webhooks
  15 SLA/Queue Mgmt          18 Knowledge Base/SOP         22 Tenant/Billing/Plans
                             21 AI Copilot                 (obs) Observability/Health
```
\* Security Posture = the existing AD/vuln/scan engine, offered as an enterprise pillar.

**Interconnection is the moat.** Every entity carries `links[]` (typed relationships),
so a Repair shows its Asset, the Asset shows its Purchase and Contract, the Contract
shows its Vendor, and every action shows in the Audit timeline.

---

## 4. Feature Breakdown by Module

### 01 · Requests / Service Catalog
- Self-service portal with **catalog items** (access, equipment, software, repair,
  procurement, onboarding/offboarding).
- **Dynamic forms** per catalog item (JSON-schema-driven), department templates.
- Per-item routing → Approvals + SLA + Queue + assignment.
- Status timeline, requester visibility, comments/mentions, attachments.
- Bulk intake, request cloning, favorites, "request on behalf of".

### 02 · Approvals Center
- Unified **pending inbox** across all modules; approve/reject/return with comment.
- **Approval matrices**: by role, department, site, business unit, and **financial
  threshold (alçada)**. Multi-stage, parallel, and conditional stages.
- Delegation (out-of-office), escalation timers, emergency fast-track, auto-approve
  rules under threshold, separation-of-duties enforcement.
- Audit-grade decision records (who/when/why/before-after), approval analytics.

### 04 · Purchases (Procurement Ops) — *upgraded*
- Purchase request intake → approval chain by alçada → PO issuance.
- **Department budgets** with real-time consumption + overspend guardrails.
- **Quote comparison** (multi-vendor, side-by-side, weighted scoring), preferred
  suppliers, smart category recommendations, recurring-purchase suggestions.
- Delivery tracking, **receiving confirmation** (full/partial), invoice attach + match
  (3-way: PO ↔ receipt ↔ invoice), emergency purchase handling.
- Procurement analytics: cycle time, bottlenecks, overdue, spend by dept/manager.

### 05 · Repairs (Maintenance Ops) — *upgraded*
- Intake → **triage** → internal vs external decision → **warranty verification**
  (auto against Contracts/Warranty) → provider assignment.
- Spare-part dependency tracking (reserve from Stock), cost estimate + **spend approval**.
- SLA deadlines, service history per asset, **recurrence detection**, lifecycle
  degradation scoring, maintenance timeline, return + **quality validation**.
- **Repair-vs-replace predictive indicator** (cost-to-date vs. residual value + age).

### 03 · Assets / Inventory
- Registration with categories, serial/patrimony/tag, **QR/barcode-ready** IDs.
- Ownership + user assignment, department allocation, location tracking, status
  lifecycle (in-stock → assigned → in-repair → retired → disposed).
- Warranty dates, maintenance history, **purchase linkage**, depreciation & lifecycle
  indicators, attachments, replacement recommendations.
- **Relationship graph**: asset ↔ request ↔ purchase ↔ repair ↔ supplier ↔ contract ↔ device.

### 06 · Vendors / Suppliers
- Profiles, contacts, documents, categories/tags; contract associations, quote history.
- **Reliability score** (on-time %, price competitiveness, response time, defect rate),
  performance dashboard, blacklist/blocked vendors with reason + audit.

### 07 · Contracts / Warranties
- Repository with document **versioning**; warranty/coverage start-end, SLA terms.
- Linked assets + suppliers, coverage mapping, compliance checklist.
- **Renewal & expiration auto-alerts** (configurable lead time), obligation calendar.

### 08 · Stock / Warehouse / Spare Parts
- Warehouse locations, counts, min thresholds, reserve stock, transfers with movement
  history, **repair-linked consumption**, replenishment suggestions, low-stock alerts,
  stock valuation (FIFO/avg cost).

### 09 · Devices / Hosts
- Registry for Windows + Linux: hostname, OS/version, IP/MAC, owner, dept, status.
- **Heartbeat / last check-in** (online/offline), installed software, patch status,
  hardware summary, **security posture indicators** (reuse scan/findings), maintenance
  windows, compliance state, grouping by tags/teams/sites/BUs.
- **Remote-action architecture as safe placeholders** (command dispatched to an
  *agent/connector*, RBAC + confirmation + audit; the platform never executes
  privileged remote code directly).

### 10 · Software / Package Management
- Approved catalog, installed inventory, **version drift**, deployment policies,
  assignment by group, software request workflow, blocked-software flags, package
  approval states, dependency awareness, **rollout rings**, rollback readiness.

### 11 · Patch / Update Management
- Patch **rings** + maintenance windows, compliance dashboard, pending/failed
  deployments, reboot-required, exception handling, criticality-based rollout,
  approval before broad rollout, per-device/per-group visibility, exec metrics.

### 12 · Compliance / Policy Center
- Policy templates + assignment to users/devices/depts/groups; compliance checks,
  exceptions register (with expiry + reason + audit), policy conflict detection,
  enforcement status, **security baseline mapping**, audit evidence, non-compliance
  alerts, remediation workflows. (Feeds from and extends the existing findings engine.)

### 13 · Automation / Workflow Builder *(flagship differentiator)*
- Visual, low-code builder: **triggers** (event, schedule, webhook, threshold),
  **conditions** (rule blocks), **actions** (notify, assign, approve, create/update
  entity, call API, run connector, dispatch remote action, escalate SLA).
- Reusable templates, versioning, dry-run/simulation, execution history, guardrails.

### 14 · Notifications / Communication Hub
- In-app center, email templates, digests, mentions/comments, approval reminders,
  escalation/overdue alerts, webhook dispatch, **per-user per-channel preferences**.

### 15 · SLA / Queue Management
- Queues + assignment rules (round-robin, skill, load), SLA policies, breach warnings,
  aging, priority handling, workload distribution, queue-health dashboard.

### 16 · Reports / Executive Analytics
- Operational + leadership views: cycle times, approval bottlenecks, repair TAT,
  assets by lifecycle, vendor performance, compliance trends, SLA attainment, queue
  perf, workload, aging, cost by dept, exception reports, **executive scorecards**,
  drill-down, exports, **scheduled delivery**.

### 17 · Audit / Activity Center *(enterprise-grade)*
- Append-only, hash-chained audit; who/what/when/where/why + **before/after**;
  security-sensitive action tagging; searchable timeline; filter by entity/module/
  user/action/date/severity; tamper-evident export for auditors.

### 18 · Knowledge Base / SOP
- Versioned articles, categories, SOPs, repair guides, procurement policy, approval
  guidelines; **smart recommendations** linked contextually into workflows.

### 19 · Identity / RBAC / Scopes  → see §5
### 20 · API / Integrations / Webhooks  → see §16
### 21 · AI Copilot  → see §18
### 22 · Tenant / Billing / Plans  → see §19

---

## 5. Role & Permission Model

**Model:** RBAC **+ ABAC scopes** (least privilege, separation of duties). Extends the
existing capability model.

- **Permission** = `resource:action` (e.g., `purchase:approve`, `asset:write`,
  `device:remote_action`, `report:export`, `tenant:admin`).
- **Role** = named set of permissions (custom per tenant).
- **Scope tags** = data-boundary attributes: `tenant`, `business_unit`, `site`,
  `department`, `queue`, `sensitivity`. Every query is scope-filtered server-side.
- **Authority level (alçada)** = numeric financial ceiling attached to a role/user for
  approvals.

**Built-in role archetypes (tenant-customizable):**

| Role | Typical scope | Highlights |
|---|---|---|
| Requester | self | create requests, view own |
| Approver | dept/BU + alçada | approve within threshold |
| Ops Agent | queue/site | work items, repairs, assets |
| Procurement | dept/BU | POs, vendors, budgets |
| Asset Manager | site/BU | asset lifecycle, contracts |
| Device Admin | tag/team | device/software/patch (actions gated) |
| Compliance Officer | tenant (read) + policy:write | policies, exceptions, audit read |
| Auditor | tenant (read-only) | audit export, no mutations |
| Tenant Admin | tenant | RBAC, plans, branding, integrations |
| Platform (provider) | cross-tenant (guarded) | support with break-glass audit |

**Controls:** delegated administration, SoD rules (e.g., requester ≠ approver ≠
receiver on the same PO), admin approval + MFA step-up for sensitive actions (remote
action, RBAC change, billing), just-in-time elevation with expiry.

---

## 6. User Journeys (representative)

1. **New laptop, end-to-end:** Employee opens *Request → Equipment*. Dynamic form →
   Approvals (manager < R$X auto, above → finance). Approved → Purchase (quote compare,
   PO) → Receiving → **Asset auto-created** and linked → enrolled as **Device** →
   Compliance/Software policies applied → warranty tracked in Contracts. One thread.
2. **Repair with warranty:** Agent logs Repair on Asset → warranty auto-checked
   (in-warranty → external RMA path; out → internal + spare-part reserve from Stock) →
   cost estimate → spend approval → SLA clock → return + quality check → service history
   updated → recurrence detector flags "3rd repair in 90d → replace".
3. **Approver's morning:** Approvals inbox, sorted by SLA risk; bulk-approve low-risk;
   AI copilot summarizes a borderline PO ("2nd emergency this month, vendor reliability
   72%, budget 88% consumed"); delegate while traveling.
4. **Compliance audit:** Auditor filters Audit Center by module/date, exports a
   tamper-evident package; Compliance Officer resolves exceptions before renewal.
5. **Executive review:** CFO opens scorecard — procurement cycle down 18%, top
   bottleneck stage, spend by dept, SLA attainment; schedules weekly email.

---

## 7. Workflows (engine model)

**Workflow = Trigger → [Conditions] → Actions**, versioned, tenant-scoped, simulatable.

- **Triggers:** entity.created/updated/status_changed, schedule (cron), webhook,
  threshold breach (budget, SLA, stock), approval decided.
- **Conditions:** field comparisons, scope checks, rule groups (AND/OR), amount/alçada.
- **Actions:** create/update entity, route approval, assign to queue/user, notify
  (channel), call outbound API, run connector job, dispatch remote action (gated),
  escalate SLA, write audit note, open Repair/Purchase, apply policy.
- **Canonical prebuilt flows:** PO approval matrix; repair-vs-replace escalation; stock
  low → replenishment PO draft; contract T-30 renewal; device non-compliant →
  remediation task; onboarding checklist fan-out.

Execution is durable (Celery today; **Temporal** at scale) with retries, idempotency
keys, and full run history.

---

## 8. Data Entities (relational core)

Core tables (all carry `tenant_id`, `created_at/by`, `updated_at/by`, soft-delete, and
emit audit events). Typed relationships via a polymorphic `entity_links` table.

```
tenants, plans, subscriptions, feature_flags, usage_counters
users, groups, roles, permissions, role_permissions, user_roles,
  scopes(business_unit, site, department), user_scopes, authority_levels
requests, catalog_items, dynamic_forms
approvals, approval_matrices, approval_stages, approval_decisions
purchases(purchase_orders), po_lines, budgets, budget_entries, quotes, receipts, invoices
repairs, repair_parts, service_providers, repair_estimates
assets, asset_categories, asset_events(lifecycle)
vendors, vendor_ratings, vendor_contacts, vendor_documents
contracts, contract_versions, warranties, obligations
stock_items, warehouses, stock_movements, stock_reservations
devices, device_software, device_patches, device_heartbeats, device_groups
software_catalog, deployments, rollout_rings
patches, patch_rings, maintenance_windows, patch_exceptions
policies, policy_assignments, compliance_checks, compliance_exceptions
workflows, workflow_versions, workflow_runs, automation_rules
notifications, notification_prefs, email_templates
sla_policies, queues, queue_items
reports, saved_views, dashboards, scorecards, scheduled_reports
audit_log (hash-chained), activity_feed
kb_articles, kb_versions, kb_categories
security_findings, finding_ingestions   ← reused from current platform
entity_links (from_type,from_id,to_type,to_id,relation)  ← the interconnection layer
```

**Multi-tenant isolation:** `tenant_id` on every row + **Postgres Row-Level Security**
policies keyed to the request's tenant claim; large/enterprise tenants can be promoted
to a **dedicated schema or database** (hybrid pool-and-silo).

---

## 9. Screen Map

```
/ (Home)                  Command center: my work, approvals-at-risk, KPIs, AI digest
/requests                 Catalog + my requests + new request (dynamic form)
/approvals                Unified inbox · matrices · delegation · analytics
/purchases                Pipeline board + PO detail (quotes/receipt/invoice) + budgets
/repairs                  Kanban triage + repair detail + service history + timeline
/assets                   Grid + asset 360 (relationship graph, lifecycle, docs)
/vendors                  List + vendor 360 (score, quotes, contracts, docs)
/contracts                Repository + renewal calendar + coverage map
/stock                    Warehouses + items + movements + reservations
/devices                  Fleet grid + device 360 (posture, software, patch, actions)
/software                 Catalog + inventory + drift + deployments/rings
/patch                    Compliance dashboard + rings + windows + exceptions
/compliance               Policies + assignments + checks + exceptions + evidence
/automation               Workflow builder (canvas) + templates + run history
/reports                  Explorer + scorecards + scheduled + exports
/audit                    Timeline + advanced filters + export
/knowledge                KB browser + editor (versioned)
/security                 (pillar) posture, findings, scans, endpoints  ← existing
/admin/*                  Users/Roles/Scopes · Tenant · Branding · Billing · Integrations · API keys
/help                     Interactive 3D guided tour (existing)
```

**Shared UX primitives on every entity:** header with status chip + contextual actions,
**detail drawer**, relationship panel, activity/audit tab, comments, attachments, saved
views, bulk triage.

---

## 10. UI/UX Direction

- **Design language:** premium Dark-Ops console (already established: theming with
  Dante/Vergil accents, glassy cards, motion) + a clean light mode. Token-based theming,
  per-tenant branding (logo, accent, favicon).
- **Navigation:** collapsible grouped sidebar (built), **command palette (Ctrl-K, built)**,
  global search across entities, breadcrumb + context switcher (tenant/BU/site).
- **Data-dense but readable:** virtualized tables, column presets, **saved filters &
  smart views**, inline edit, bulk actions with RBAC + audit, sticky summaries.
- **Detail drawers** over full-page reloads; contextual actions; keyboard-first.
- **Dashboards:** customizable widgets, drill-down, sparklines (built), SVG export
  (built), scorecards.
- **Craft states:** elegant empty states, skeleton loaders, structured error states,
  optimistic updates, guided onboarding checklist, in-app **3D guided tour (built)**.
- **Accessibility:** WCAG 2.1 AA target — focus rings, ARIA, keyboard nav, reduced-motion
  (already honored), contrast-checked tokens.
- **Mobile-adaptive** for approvals/queue/field repairs (responsive, PWA later).

---

## 11. Monetizable Premium Differentiators

| Differentiator | Tier |
|---|---|
| Core requests, approvals, assets, basic reports | Starter |
| Purchases + Repairs + Vendors + Contracts + Stock | Professional |
| **Automation/Workflow builder**, SLA/Queues, advanced analytics, scheduled reports | Business |
| **AI Copilot**, **Compliance & Security Posture pillar**, Device/Patch/Software, advanced audit export, multi-level approval matrices, API + webhooks | Enterprise |
| SSO/SAML/OIDC, white-label, dedicated tenancy, premium support, custom SLAs | Enterprise add-ons |

**Usage-metered upsell:** seats, active devices, workflow runs, AI copilot tokens, API
call volume, storage.

---

## 12. Recommended Stack (production-grade)

**Frontend**
- React 18 + TypeScript + **Vite** (SPA; Next.js only if we need SSR marketing/portal).
- **TanStack Query** (server state) + Zustand (light UI state); TanStack Table +
  Virtual for grids; **React Hook Form + Zod** for schema-driven forms.
- Design system: headless **Radix UI** + tokenized CSS (current theme engine) → package
  as an internal component library; Storybook.
- Charts: **Recharts** (built) + lightweight SVG for sparklines (built); ECharts if we
  need heavy dataviz. **i18n:** `i18next` (pt-BR + en to start).
- Workflow canvas: **React Flow**. Command palette (built). PWA for mobile.

**Backend**
- **FastAPI** (async) + SQLModel/SQLAlchemy 2 + Pydantic v2 (all current).
- Modular **domain services** (bounded contexts: procurement, maintenance, assets,
  identity, workflow, compliance) behind a versioned REST API (`/api/v1`) + OpenAPI;
  optional GraphQL gateway later for flexible reporting reads.
- Auth: JWT (access+refresh, rotation — built) + MFA (built) + **OIDC/SAML** (Authentik/
  Keycloak or Auth0/Entra) for enterprise SSO.
- **Workflow/orchestration:** Celery + Redis now → **Temporal** for durable, versioned,
  long-running workflows at scale.
- File storage: **S3-compatible (MinIO self-host / AWS S3)** with signed URLs + AV scan.
- Notifications engine: template service + channel adapters (email/SMTP built, Teams/
  Slack/Chat built, webhooks built).
- Search: **OpenSearch/Elasticsearch** for cross-entity search & audit timelines.
- Caching/rate-limit/locks: **Redis** (built).

**Database**
- **PostgreSQL** primary, normalized relational core + **RLS** multi-tenant isolation;
  JSONB for dynamic forms/evidence (already used).
- Audit: append-only, **hash-chained** table (+ optional WORM object export).
- Reporting: read replicas → for scale, CDC (Debezium) into a **columnar warehouse**
  (ClickHouse / DuckDB / BigQuery) for analytics; materialized views for common KPIs.

**Infrastructure**
- Containers (built) → **Kubernetes** (Helm) for scale; Docker Compose/Swarm for SMB
  self-host. CI/CD: GitHub Actions (build, SAST, dep-scan, image-scan, sign, SBOM).
- Observability: **OpenTelemetry** → Prometheus + Grafana + Loki + Tempo; Sentry for
  errors. Health checks (built).
- Secrets: Vault / cloud KMS (Docker Secrets today). Object storage: S3/MinIO. Reverse
  proxy: NGINX/Traefik (external NPM today). Background workers: Celery/Temporal.
- Backup/DR: nightly PITR (WAL), cross-region replica, tested restores; RPO ≤ 15 min,
  RTO ≤ 1 h for Enterprise.

---

## 13. Architecture Strategy

- **Modular monolith first, service-extraction later.** Ship the suite as one FastAPI
  app with clean domain modules and a shared kernel (auth, audit, links, tenancy).
  Extract the hottest domains (workflow, reporting, notifications) into services when
  load/team size justifies it.
- **Event backbone:** every mutation emits a domain event (outbox pattern → Redis/Kafka)
  consumed by audit, search indexer, notifications, automation, and analytics — this is
  what makes modules *feel interconnected*.
- **Tenancy:** pool model with RLS by default; silo (dedicated schema/DB) for Enterprise.
  Tenant context resolved from JWT + subdomain; enforced in a middleware + RLS.
- **API-first:** OpenAPI contract, SDK generation, idempotency keys, cursor pagination,
  field selection, ETag caching (gzip built).
- **Extensibility:** connector framework (typed adapters), webhook subscriptions,
  workflow custom actions, sandboxed script hooks (no arbitrary RCE — allow-listed).

---

## 14. Security Model (Zero-Trust aligned)

- **Identity:** MFA (built), SSO (OIDC/SAML), step-up auth for sensitive actions,
  short-lived tokens with rotation (built), admin session controls + break-glass.
- **Authorization:** deny-by-default RBAC + ABAC scopes enforced **server-side + RLS**;
  SoD rules; JIT elevation with expiry; export/download authorization + audit (built
  pattern).
- **Tenant isolation:** RLS + tenant-scoped storage prefixes + per-tenant audit
  boundaries + encryption keys per tenant (envelope encryption) for Enterprise.
- **Data protection:** TLS everywhere (built), encryption at rest (DB + object store),
  field-level encryption/masking for sensitive data (secret masking already built in
  findings), PII minimization.
- **App hardening:** strict input validation (Pydantic/Zod), output encoding, CSP/secure
  headers (built), rate limiting (built), SSRF/command-injection/path-traversal guards
  (already applied in scan/ingest modules), safe subprocess (allow-listed, non-root
  containers, dropped caps — built).
- **Supply chain:** SAST + dep-scan + image-scan + secret-scan + SBOM in CI (the
  findings engine can dogfood this), pinned deps, signed artifacts.
- **Auditability:** hash-chained audit, tamper-evident exports, immutable retention
  option (S3 Object Lock) for regulated tenants.

---

## 15. Automation Model

- **Rule engine + workflow engine** (see §7). Low-code canvas (React Flow) →
  serialized graph → validated → executed on Temporal/Celery with idempotency + retries.
- **Guardrails:** every automated action respects RBAC/scopes and is audited as
  "system on behalf of policy X"; remote/privileged actions require pre-approval and go
  through the connector/agent boundary, never direct execution from the web tier.
- **Marketplace-ready templates** (procurement approval, renewal, repair escalation,
  onboarding) shippable per plan.

---

## 16. Integration Model

- **REST API v1** (OpenAPI) + **webhooks** (subscriptions, signed payloads, retries) +
  **CSV/XLSX import/export** with validation (safe-parse pattern already built).
- **Identity/dir:** Microsoft **Entra ID / 365**, **Active Directory / LDAP** (built),
  Google Workspace.
- **Comms:** Teams, Slack, Google Chat (built), SMTP/email providers.
- **ERP/Finance:** connector adapters (SAP/TOTVS/NetSuite) for PO/invoice sync.
- **CMDB/Asset & Monitoring:** import adapters (Zabbix/Prometheus/Wazuh — some built),
  MDM connectors (Intune/Jamf) for device truth.
- **Security scanners:** Trivy/Grype/Gitleaks/npm/pip/Lynis normalized ingestion (built)
  → doubles as the compliance evidence pipeline.
- **Connector framework:** typed, credential-vaulted, health-monitored, per-tenant.

---

## 17. Reporting Strategy

- **Three layers:** (1) operational live queries (Postgres + materialized views), (2)
  saved views/dashboards per user/tenant, (3) analytics warehouse (ClickHouse/DuckDB via
  CDC) for heavy cross-module and historical trend analysis.
- **Deliverables:** executive scorecards, drill-down dashboards, aging/exception
  reports, scheduled email/Chat delivery, exports (CSV/XLSX/PDF — SVG-chart PDF export
  already built), and an embeddable read API for BI tools.
- **KPI catalog:** procurement cycle time, approval bottleneck stage, repair TAT,
  repair-vs-replace rate, asset lifecycle distribution, vendor score trend, SLA
  attainment, queue health, compliance %, spend by dept, MTTR for findings.

---

## 18. AI Copilot Opportunities

- **Record summarization** (PO/repair/asset 360 in one paragraph).
- **Bottleneck & anomaly explanation** ("approvals stall at Finance stage; avg +2.3d").
- **Next-best-action** and **supplier recommendation** (score + price + history).
- **Repair-pattern & repair-vs-replace** guidance; **policy-conflict** flagging.
- **Draft approval comments / KB articles**; **workflow suggestions** from usage.
- **Natural-language ops Q&A** across modules (RAG over tenant data with strict
  scope/RBAC filtering — the copilot only sees what the *user* may see).
- **Guardrails:** read-mostly by default; any action it proposes runs through the same
  RBAC + confirmation + audit path. Token usage metered per plan.

---

## 19. SaaS Commercialization Strategy

**Tiers:** Starter → Professional → Business → Enterprise (feature flags + quotas per
plan; module-based upsell; seat + usage metering; free trial; white-label add-on).

- **Billing readiness:** Stripe (or local: e.g., Iugu/Pagar.me for BR) — plans,
  proration, invoices, dunning; usage counters (seats, devices, workflow runs, AI
  tokens, storage). Entitlements service gates features server-side (never trust client).
- **Tenant lifecycle:** self-serve signup → guided onboarding → trial → convert →
  expand (module upsell) → renewal. In-app upgrade prompts at quota edges.
- **Packaging levers:** advanced analytics, automation builder, AI copilot, compliance/
  security pillar, API access, advanced audit export, multi-level approvals, SSO/SAML,
  white-label, premium support & SLAs.
- **GTM:** land with Purchases+Approvals+Assets (finance-visible ROI), expand to
  Repairs+Devices+Compliance, upsell Security+AI. Reference the existing Astra
  deployment as design-partner proof.

---

## 20. Phased Roadmap

**Phase 0 — Foundation hardening (reuse what exists) · ~4–6 wks**
- Introduce `tenant_id` + Postgres RLS across the schema; tenant context middleware.
- Generalize RBAC into RBAC+ABAC scopes; entitlement/feature-flag service.
- `entity_links` interconnection table; unify audit into the enterprise Audit Center.
- Object storage (MinIO/S3) + attachments; notification templates abstraction.

**Phase 1 — MVP (sellable) · ~8–12 wks**
- Modules: **Requests/Catalog, Approvals (matrices+alçada), Purchases, Assets**, basic
  Reports, Audit Center, Identity/RBAC/Scopes, Tenant admin + branding + billing (trial),
  Notifications, Knowledge Base. Onboarding + command palette + saved views (mostly built).
- *Goal: a company can run intake → approval → purchase → asset, fully audited, multi-tenant.*

**Phase 2 — V2 (stickiness & margin) · ~12–16 wks**
- **Repairs + Vendors + Contracts + Stock** (full lifecycle graph), **SLA/Queues**,
  **Automation/Workflow builder v1**, advanced analytics + scorecards + scheduled
  reports, webhooks + public API v1, saved smart views everywhere.

**Phase 3 — Enterprise · ~16–24 wks**
- **Devices/Hosts + Software + Patch** (connectors to MDM/AD), **Compliance/Policy
  Center** + **Security Posture pillar** (existing findings/scan engine productized),
  **AI Copilot**, SSO/SAML/OIDC, dedicated tenancy option, white-label, advanced audit
  export (WORM), Temporal-backed workflows, analytics warehouse (CDC), premium support.

**Phase 4 — Scale & ecosystem**
- Connector marketplace, workflow template marketplace, mobile PWA/field app, regional
  data residency, partner/reseller program.

---

## Appendix A — "Definition of premium" checklist
Interconnected entity graph · audit on every action · scope-safe multi-tenancy ·
low-code automation · AI copilot that respects RBAC · saved views + command palette ·
drill-down analytics + scheduled delivery · SSO + MFA + step-up · white-label ·
metered billing · elegant empty/loading/error states · keyboard-first · dark+light.

## Appendix B — Immediate next engineering steps
1. Add `tenant_id` + RLS migration scaffold (reversible) and tenant middleware.
2. Ship `entity_links` + a generic "relationships" panel component.
3. Extract entitlement/feature-flag service (gate a first premium module).
4. Prototype the Requests→Approvals→Purchase→Asset thread on the current stack.
5. Stand up MinIO + attachments + AV scan; unify audit UI.
