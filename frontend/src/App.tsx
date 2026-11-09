import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import { ToastProvider } from './components/ToastProvider'
import { AppShell } from './layout/AppShell'
import { JobsPage } from './pages/jobs/JobsPage'
import { UpcomingPage } from './pages/UpcomingPage'

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/vagas" replace />} />
            <Route path="vagas" element={<JobsPage />} />
            <Route
              path="kanban"
              element={
                <UpcomingPage
                  title="Kanban"
                  description="O quadro das suas candidaturas chega no próximo passo da Fase 4. As vagas que você marcar com interesse vão aparecer aqui."
                />
              }
            />
            <Route
              path="empresas"
              element={
                <UpcomingPage
                  title="Empresas"
                  description="A tela de empresas monitoradas chega em breve. Por enquanto, use python -m app.companies no backend."
                />
              }
            />
            <Route
              path="perfil"
              element={
                <UpcomingPage
                  title="Perfil"
                  description="A edição do perfil chega em breve. Por enquanto, edite backend/profile.toml e rode python -m app.profile import."
                />
              }
            />
            <Route path="*" element={<Navigate to="/vagas" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}
