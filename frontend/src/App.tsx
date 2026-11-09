import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import { ToastProvider } from './components/ToastProvider'
import { AppShell } from './layout/AppShell'
import { CompaniesPage } from './pages/companies/CompaniesPage'
import { JobsPage } from './pages/jobs/JobsPage'
import { KanbanPage } from './pages/kanban/KanbanPage'
import { ProfilePage } from './pages/profile/ProfilePage'

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/vagas" replace />} />
            <Route path="vagas" element={<JobsPage />} />
            <Route path="kanban" element={<KanbanPage />} />
            <Route path="empresas" element={<CompaniesPage />} />
            <Route path="perfil" element={<ProfilePage />} />
            <Route path="*" element={<Navigate to="/vagas" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}
