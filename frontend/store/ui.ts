import { create } from 'zustand'

export type SidebarSection =
  | 'dashboard' | 'clients' | 'leads' | 'properties' | 'deals'
  | 'documents' | 'compliance' | 'operations' | 'knowledge' | 'ai'
  | 'regulations' | 'analytics' | 'executive' | 'autonomous' | 'admin'
  | 'accounting-events' | 'accounting-decisions' | 'accounting-replay'
  | 'ledger-entries' | 'ledger-accounts' | 'ledger-periods'
  | 'tax-registers' | 'tax-assignments' | 'tax-policies'
  | 'tax-optimization'
  | 'reports-drafts' | 'reports-templates' | 'reports-audit'
  | 'reconciliation-runs' | 'reconciliation-matches' | 'reconciliation-gaps'
  | 'control-actions' | 'control-approval' | 'control-state' | 'control-metrics'
  | 'imports-bank' | 'imports-documents' | 'imports-ocr' | 'imports-history'
  | 'companies'
  | 'obligations'

interface UIState {
  sidebar: 'expanded' | 'collapsed'
  theme: 'light' | 'dark'
  currentDealId: string | null
  copilotOpen: boolean
  activeSection: SidebarSection
  toggleSidebar: () => void
  setTheme: (theme: 'light' | 'dark') => void
  setCurrentDeal: (id: string | null) => void
  setCopilotOpen: (open: boolean) => void
  setActiveSection: (section: SidebarSection) => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebar: 'expanded',
  theme: 'light',
  currentDealId: null,
  copilotOpen: false,
  activeSection: 'dashboard',
  toggleSidebar: () => set((s) => ({ sidebar: s.sidebar === 'expanded' ? 'collapsed' : 'expanded' })),
  setTheme: (theme) => set({ theme }),
  setCurrentDeal: (id) => set({ currentDealId: id }),
  setCopilotOpen: (open) => set({ copilotOpen: open }),
  setActiveSection: (section) => set({ activeSection: section }),
}))
