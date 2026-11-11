import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Result, Button } from 'antd';
import AppLayout from './layout/AppLayout';
import { sections, homePath } from './routes';
import { useSession } from './session/SessionContext';
import { FullScreenSkeleton, PageSkeleton } from './components/Skeletons';
import Forbidden from './pages/Forbidden';
import NotFound from './pages/NotFound';

const Login = lazy(() => import('./pages/Login'));
const Placeholder = lazy(() => import('./pages/Placeholder'));
const pages = {
  'my-workload': lazy(() => import('./pages/MyWorkload')),
  'my-survey': lazy(() => import('./pages/DailySurvey')),
  dashboard: lazy(() => import('./pages/Dashboard')),
  plans: lazy(() => import('./pages/Plans')),
  analytics: lazy(() => import('./pages/TeacherAnalytics')),
  'work-types': lazy(() => import('./pages/WorkTypes')),
  schools: lazy(() => import('./pages/Schools')),
  reports: lazy(() => import('./pages/Reports')),
  users: lazy(() => import('./pages/Users')),
};

const AnalyticsPage = pages.analytics;

function Guard({ section, children }) {
  const { role } = useSession();
  const s = sections.find((x) => x.key === section);
  if (!s.roles.includes(role)) return <Forbidden />;
  return <Suspense fallback={<PageSkeleton narrow={s.narrow} />}>{children}</Suspense>;
}

export default function App() {
  const session = useSession();
  const location = useLocation();

  if (session.status === 'loading') return <FullScreenSkeleton />;
  if (session.status === 'error') {
    return (
      <Result
        status="warning"
        title="Не удалось загрузить профиль"
        subTitle={session.error?.message}
        extra={<Button onClick={session.logout}>Войти заново</Button>}
      />
    );
  }
  if (session.status === 'anonymous') {
    return (
      <Suspense fallback={<FullScreenSkeleton />}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Navigate to="/login" replace state={{ from: location.pathname }} />} />
        </Routes>
      </Suspense>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Navigate to={location.state?.from ?? homePath[session.role]} replace />} />
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to={homePath[session.role] ?? '/'} replace />} />
        {sections.map((s) => {
          const Page = pages[s.key];
          return (
            <Route
              key={s.key}
              path={s.path.slice(1)}
              element={<Guard section={s.key}>{Page ? <Page /> : <Placeholder section={s.key} />}</Guard>}
            />
          );
        })}
        <Route path="analytics/teachers/:teacherId" element={<Guard section="analytics"><AnalyticsPage /></Guard>} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
