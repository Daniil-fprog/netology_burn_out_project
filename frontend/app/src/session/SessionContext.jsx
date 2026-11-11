import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from '../api/endpoints';
import { clearToken, getToken, setToken } from '../api/tokenStore';
import { setUnauthorizedHandler } from '../api/http';

const ROLE_PRIORITY = ['system_admin', 'group_head', 'head', 'director', 'teacher'];
export const ROLE_LABELS = {
  teacher: 'Преподаватель',
  director: 'Директор',
  head: 'Глава',
  group_head: 'Глава группы',
  system_admin: 'Администратор',
};

const SCHOOL_KEY = 'school_id';
const readSchool = () => { try { return localStorage.getItem(SCHOOL_KEY); } catch { return null; } };

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const qc = useQueryClient();
  const [token, setTokenState] = useState(getToken);
  const [schoolId, setSchoolIdState] = useState(readSchool);

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
    qc.clear();
  }, [qc]);

  useEffect(() => { setUnauthorizedHandler(logout); }, [logout]);

  const sessionQuery = useQuery({
    queryKey: ['session', token],
    enabled: Boolean(token),
    staleTime: Infinity,
    queryFn: async ({ signal }) => {
      const [me, access] = await Promise.all([authApi.me({ signal }), authApi.access({ signal })]);
      return { me, access };
    },
  });

  const login = useCallback(async (loginName, password) => {
    const res = await authApi.login(loginName, password);
    qc.clear();
    setToken(res.access_token);
    setTokenState(res.access_token);
  }, [qc]);

  const setSchoolId = useCallback((id) => {
    setSchoolIdState(id);
    try { localStorage.setItem(SCHOOL_KEY, id); } catch {}
  }, []);

  const value = useMemo(() => {
    if (!token) return { status: 'anonymous', login, logout };
    if (sessionQuery.isPending) return { status: 'loading', login, logout };
    if (sessionQuery.isError) return { status: 'error', error: sessionQuery.error, login, logout };
    const { me, access } = sessionQuery.data;
    const role = ROLE_PRIORITY.find((r) => access.roles.includes(r)) ?? null;
    const schools = access.schools;
    const school = schools.find((s) => s.id === schoolId) ?? schools[0] ?? null;
    return {
      status: 'ready',
      user: me,
      role,
      roleLabel: ROLE_LABELS[role],
      roles: access.roles,
      schools,
      school,
      teacherId: school?.teacher_id ?? null,
      setSchoolId,
      login,
      logout,
    };
  }, [token, sessionQuery.isPending, sessionQuery.isError, sessionQuery.error, sessionQuery.data, schoolId, login, logout, setSchoolId]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export const useSession = () => useContext(SessionContext);
