'use client'
import Link from 'next/link'
import { useUIStore } from '@store/ui'
import { useAuthStore } from '@store/auth'
import { cn } from '@/lib/utils'

const navItems = [
  { section: 'dashboard', label: 'Дашборд', href: '/', icon: '\u25FB' },
  // ── Accounting Core ──
  { section: 'accounting-events', label: 'События', href: '/accounting/events', icon: '\u25A3', group: 'Бухгалтерия' },
  { section: 'accounting-decisions', label: 'Решения', href: '/accounting/decisions', icon: '\u25C7', group: 'Бухгалтерия' },
  { section: 'accounting-replay', label: 'Пересчёт', href: '/accounting/replay', icon: '\u21BB', group: 'Бухгалтерия' },
  // ── Ledger ──
  { section: 'ledger-entries', label: 'Проводки', href: '/ledger/entries', icon: '\u25C8', group: 'Главная книга' },
  { section: 'ledger-accounts', label: 'Счета', href: '/ledger/accounts', icon: '\u25A1', group: 'Главная книга' },
  { section: 'ledger-periods', label: 'Периоды', href: '/ledger/periods', icon: '\u25CB', group: 'Главная книга' },
  // ── Tax ──
  { section: 'tax-registers', label: 'Регистры', href: '/tax/registers', icon: '\u2B22', group: 'Налоги' },
  { section: 'tax-assignments', label: 'Назначения', href: '/tax/assignments', icon: '\u21C4', group: 'Налоги' },
  { section: 'tax-policies', label: 'Политики', href: '/tax/policies', icon: '\u2696', group: 'Налоги' },
  { section: 'tax-optimization', label: 'Оптимизация', href: '/tax/optimization', icon: '\u26A1', group: 'Налоги' },
  // ── Reports ──
  { section: 'reports-drafts', label: 'Черновики', href: '/reports/drafts', icon: '\u2630', group: 'Отчёты' },
  { section: 'reports-templates', label: 'Шаблоны', href: '/reports/templates', icon: '\u2714', group: 'Отчёты' },
  { section: 'reports-audit', label: 'Аудит', href: '/reports/audit', icon: '\u2606', group: 'Отчёты' },
  // ── Reconciliation ──
  { section: 'reconciliation-runs', label: 'Запуски', href: '/reconciliation/runs', icon: '\u2691', group: 'Сверка' },
  { section: 'reconciliation-matches', label: 'Сопоставления', href: '/reconciliation/matches', icon: '\u2713', group: 'Сверка' },
  { section: 'reconciliation-gaps', label: 'Расхождения', href: '/reconciliation/gaps', icon: '\u26A0', group: 'Сверка' },
  // ── Control Plane ──
  { section: 'control-actions', label: 'Действия', href: '/control/actions', icon: '\u2699', group: 'Управление' },
  { section: 'control-approval', label: 'Согласование', href: '/control/approval', icon: '\u2714', group: 'Управление' },
  { section: 'control-state', label: 'Состояние', href: '/control/state', icon: '\u2693', group: 'Управление' },
  { section: 'control-metrics', label: 'Метрики', href: '/control/metrics', icon: '\u2261', group: 'Управление' },
  // ── Imports ──
  { section: 'imports-bank', label: 'Импорт банка', href: '/imports', icon: '\u21E7', group: 'Импорт' },
  { section: 'imports-documents', label: 'Документы', href: '/imports/documents', icon: '\u25A3', group: 'Импорт' },
  { section: 'imports-ocr', label: 'OCR очередь', href: '/imports/ocr', icon: '\u2316', group: 'Импорт' },
  { section: 'imports-history', label: 'История импорта', href: '/imports/history', icon: '\u23F0', group: 'Импорт' },
  { section: 'companies', label: 'Компании', href: '/companies', icon: '\u26B2', group: 'Настройки' },
  // ── Calendar ──
  { section: 'obligations', label: 'Обязательства', href: '/obligations', icon: '\uD83D\uDCC5', group: 'Календарь' },
]

// CRM items (collapsible under "CRM")
const crmItems = [
  { section: 'clients', label: 'Клиенты', href: '/clients', icon: '\u25C9' },
  { section: 'leads', label: 'Leads', href: '/leads', icon: '\u2B21' },
  { section: 'properties', label: 'Объекты', href: '/properties', icon: '\u25C7' },
  { section: 'deals', label: 'Сделки', href: '/deals', icon: '\u25C6' },
  { section: 'documents', label: 'Документы', href: '/documents', icon: '\u25A3' },
  { section: 'compliance', label: 'Комплаенс', href: '/compliance', icon: '\u2696' },
  { section: 'operations', label: 'Операции', href: '/operations', icon: '\u2699' },
]

export function Sidebar() {
  const { sidebar, activeSection, setActiveSection } = useUIStore()
  const { user } = useAuthStore()
  const collapsed = sidebar === 'collapsed'

  // Render a nav item
  const NavLink = ({ item }: { item: typeof navItems[0] }) => (
    <Link key={item.section} href={item.href}
      onClick={() => setActiveSection(item.section as any)}
      className={cn(
        'flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm transition-colors',
        activeSection === item.section
          ? 'bg-brand-100 text-brand-800 font-medium'
          : 'hover:bg-gray-100'
      )}>
      <span className="text-base w-5 text-center">{item.icon}</span>
      {!collapsed && <span>{item.label}</span>}
    </Link>
  )

  // Group items
  const groups: Record<string, typeof navItems> = {}
  for (const item of navItems) {
    if (item.group) {
      if (!groups[item.group]) groups[item.group] = []
      groups[item.group].push(item)
    }
  }

  return (
    <aside className={cn(
      'flex flex-col border-r bg-card transition-all overflow-y-auto',
      collapsed ? 'w-16' : 'w-56'
    )}>
      <div className="p-4 border-b shrink-0">
        <h2 className={cn('font-bold', collapsed && 'text-center')}>
          {collapsed ? 'R' : 'RealtorOS'}
        </h2>
      </div>
      <nav className="flex-1 p-2 space-y-3">
        {/* Dashboard */}
        <NavLink item={{ section: 'dashboard', label: 'Дашборд', href: '/', icon: '\u25FB' } as any} />

        {/* Accounting Groups */}
        {Object.entries(groups).map(([group, items]) => (
          <div key={group} className="space-y-0.5">
            {!collapsed && (
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground px-3 py-1 font-semibold">
                {group}
              </p>
            )}
            {items.map((item) => (
              <div key={item.section}>
                <NavLink item={item} />
              </div>
            ))}
          </div>
        ))}

        {/* CRM section */}
        <div className="space-y-0.5 pt-2 border-t">
          {!collapsed && (
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground px-3 py-1 font-semibold">
              CRM
            </p>
          )}
          {crmItems.map((item) => (
            <Link key={item.section} href={item.href}
              onClick={() => setActiveSection(item.section as any)}
              className={cn(
                'flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm transition-colors',
                activeSection === item.section
                  ? 'bg-brand-100 text-brand-800 font-medium'
                  : 'hover:bg-gray-100'
              )}>
              <span className="text-base w-5 text-center">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </Link>
          ))}
        </div>
      </nav>
      <div className="p-3 border-t shrink-0">
        {!collapsed && user && (
          <div className="text-xs text-muted-foreground">
            <p className="font-medium">{user.full_name}</p>
            <p>{user.role}</p>
          </div>
        )}
      </div>
    </aside>
  )
}
