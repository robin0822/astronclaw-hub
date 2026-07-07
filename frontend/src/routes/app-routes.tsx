import { lazy, Suspense, type ReactNode } from 'react';
import { LoadingOutlined } from '@ant-design/icons';
import { Spin } from 'antd';
import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from '../components/Layout';

const LoginPage = lazy(() => import('../pages/LoginPage'));
const AgentsPage = lazy(() => import('../pages/AgentsPage'));
const OrgPage = lazy(() => import('../pages/OrgPage'));
const MonitoringPage = lazy(() => import('../pages/MonitoringPage'));
const ModelsPage = lazy(() => import('../pages/ModelsPage'));
const OpsPage = lazy(() => import('../pages/OpsPage'));
const SkillsPage = lazy(() => import('../pages/SkillsPage'));
const KnowledgePage = lazy(() => import('../pages/KnowledgePage'));
const MemoryPage = lazy(() => import('../pages/MemoryPage'));
const SeatsPage = lazy(() => import('../pages/SeatsPage'));
const SharingPage = lazy(() => import('../pages/SharingPage'));
const ChannelsPage = lazy(() => import('../pages/ChannelsPage'));
const SecurityPage = lazy(() => import('../pages/SecurityPage'));
const DiagnosisPage = lazy(() => import('../pages/DiagnosisPage'));
const SharePage = lazy(() => import('../pages/SharePage'));

function PageFallback({ fullPage = false }: { fullPage?: boolean }) {
  return (
    <div className={`page-loading${fullPage ? ' full-page' : ''}`}>
      <Spin indicator={<LoadingOutlined spin />} size="large" description="页面加载中..." />
    </div>
  );
}

function SuspendedPage({ children, fullPage = false }: { children: ReactNode; fullPage?: boolean }) {
  return <Suspense fallback={<PageFallback fullPage={fullPage} />}>{children}</Suspense>;
}

function DefaultRedirect() {
  return <Navigate to="/agents" replace />;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <SuspendedPage fullPage>
            <LoginPage />
          </SuspendedPage>
        }
      />
      <Route
        path="/share/:id"
        element={
          <SuspendedPage fullPage>
            <SharePage />
          </SuspendedPage>
        }
      />
      <Route path="/" element={<Layout />}>
        <Route index element={<DefaultRedirect />} />
        <Route
          path="agents"
          element={
            <SuspendedPage>
              <AgentsPage />
            </SuspendedPage>
          }
        />
        <Route
          path="org"
          element={
            <SuspendedPage>
              <OrgPage />
            </SuspendedPage>
          }
        />
        <Route
          path="monitoring"
          element={
            <SuspendedPage>
              <MonitoringPage />
            </SuspendedPage>
          }
        />
        <Route
          path="models"
          element={
            <SuspendedPage>
              <ModelsPage />
            </SuspendedPage>
          }
        />
        <Route
          path="ops"
          element={
            <SuspendedPage>
              <OpsPage />
            </SuspendedPage>
          }
        />
        <Route
          path="skills"
          element={
            <SuspendedPage>
              <SkillsPage />
            </SuspendedPage>
          }
        />
        <Route
          path="knowledge"
          element={
            <SuspendedPage>
              <KnowledgePage />
            </SuspendedPage>
          }
        />
        <Route
          path="memory"
          element={
            <SuspendedPage>
              <MemoryPage />
            </SuspendedPage>
          }
        />
        <Route
          path="seats"
          element={
            <SuspendedPage>
              <SeatsPage />
            </SuspendedPage>
          }
        />
        <Route
          path="sharing"
          element={
            <SuspendedPage>
              <SharingPage />
            </SuspendedPage>
          }
        />
        <Route
          path="channels"
          element={
            <SuspendedPage>
              <ChannelsPage />
            </SuspendedPage>
          }
        />
        <Route
          path="security"
          element={
            <SuspendedPage>
              <SecurityPage />
            </SuspendedPage>
          }
        />
        <Route
          path="diagnosis"
          element={
            <SuspendedPage>
              <DiagnosisPage />
            </SuspendedPage>
          }
        />
        <Route path="*" element={<DefaultRedirect />} />
      </Route>
    </Routes>
  );
}
