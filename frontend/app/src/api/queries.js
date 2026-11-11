import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  adminApi, dashboardApi, exportsApi, importsApi, schoolsApi, plansApi, surveysApi, teachersApi, workloadApi, workTypesAdminApi, workTypesApi,
} from './endpoints';

export const qk = {
  workTypes: (includeArchived) => ['work-types', { includeArchived }],
  teachers: (schoolId, params) => ['schools', schoolId, 'teachers', params],
  imports: (schoolId, params) => ['schools', schoolId, 'imports', params],
  daily: (schoolId, params) => ['schools', schoolId, 'daily', params],
  dashboard: (schoolId, params) => ['schools', schoolId, 'dashboard', params],
  planItems: (schoolId, params) => ['schools', schoolId, 'plan-items', params],
  survey: (schoolId, code) => ['schools', schoolId, 'surveys', code],
  surveyResponses: (schoolId, params) => ['schools', schoolId, 'survey-responses', params],
};

export const useWorkTypes = ({ includeArchived = false } = {}) => useQuery({
  queryKey: qk.workTypes(includeArchived),
  queryFn: ({ signal }) => workTypesApi.list({ includeArchived }, { signal }),
  staleTime: 10 * 60_000,
});

export const useTeachers = (schoolId, params) => useQuery({
  queryKey: qk.teachers(schoolId, params),
  queryFn: ({ signal }) => teachersApi.list(schoolId, params, { signal }),
  enabled: Boolean(schoolId),
  placeholderData: keepPreviousData,
});

export const useImports = (schoolId, params) => useQuery({
  queryKey: qk.imports(schoolId, params),
  queryFn: ({ signal }) => importsApi.list(schoolId, params, { signal }),
  enabled: Boolean(schoolId),
  placeholderData: keepPreviousData,
});

export const useDailyRange = (schoolId, { dateFrom, dateTo, teacherId, pageSize = 31 }, { enabled = true } = {}) => useQuery({
  queryKey: qk.daily(schoolId, { dateFrom, dateTo, teacherId, pageSize }),
  queryFn: ({ signal }) => workloadApi.daily(schoolId, { dateFrom, dateTo, teacherId, sort: 'date_asc', pageSize }, { signal }),
  enabled: Boolean(schoolId) && enabled,
  placeholderData: keepPreviousData,
  staleTime: 30_000,
});

export function useSaveDay(schoolId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ recordId, body }) => (recordId
      ? workloadApi.patchDay(schoolId, recordId, body)
      : workloadApi.createDay(schoolId, body)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schools', schoolId, 'daily'] }),
  });
}

export const useSurvey = (schoolId, code) => useQuery({
  queryKey: qk.survey(schoolId, code),
  queryFn: ({ signal }) => surveysApi.get(schoolId, code, { signal }),
  enabled: Boolean(schoolId && code),
  staleTime: 60 * 60_000,
});

export const useSurveyResponses = (schoolId, params, { enabled = true } = {}) => useQuery({
  queryKey: qk.surveyResponses(schoolId, params),
  queryFn: ({ signal }) => surveysApi.responses(schoolId, params, { signal }),
  enabled: Boolean(schoolId) && enabled,
  placeholderData: keepPreviousData,
});

export function useSaveSurveyResponse(schoolId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ responseId, create, answers, submit }) => {
      if (!responseId) return surveysApi.create(schoolId, { ...create, answers, status: submit ? 'submitted' : 'draft' });
      const draft = await surveysApi.patchDraft(schoolId, responseId, answers);
      return submit ? surveysApi.submit(schoolId, responseId) : draft;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schools', schoolId, 'survey-responses'] }),
  });
}

export const useWorkTypeMutations = () => {
  const qc = useQueryClient();
  const onSuccess = () => qc.invalidateQueries({ queryKey: ['work-types'] });
  return {
    save: useMutation({
      mutationFn: ({ id, body }) => (id ? workTypesAdminApi.update(id, body) : workTypesAdminApi.create(body)),
      onSuccess,
    }),
    archive: useMutation({ mutationFn: (id) => workTypesAdminApi.archive(id), onSuccess }),
    restore: useMutation({ mutationFn: (id) => workTypesAdminApi.update(id, { is_active: true }), onSuccess }),
  };
};

export const usePlannedDashboard = (schoolId, params) => useQuery({
  queryKey: qk.dashboard(schoolId, params),
  queryFn: ({ signal }) => dashboardApi.planned(schoolId, params, { signal }),
  enabled: Boolean(schoolId && params.dateFrom && params.dateTo),
  placeholderData: keepPreviousData,
});

export const usePlanItems = (schoolId, params) => useQuery({
  queryKey: qk.planItems(schoolId, params),
  queryFn: ({ signal }) => plansApi.items(schoolId, params, { signal }),
  enabled: Boolean(schoolId),
  placeholderData: keepPreviousData,
});

export const useAllTeachers = (schoolId) => useTeachers(schoolId, { page: 1, pageSize: 200 });

export function useImportMutations(schoolId) {
  const qc = useQueryClient();
  return {
    validate: useMutation({ mutationFn: (form) => plansApi.validate(schoolId, form) }),
    commit: useMutation({
      mutationFn: (form) => plansApi.import(schoolId, form),
      onSuccess: () => qc.invalidateQueries({ queryKey: ['schools', schoolId] }),
    }),
  };
}

export const useSchools = () => useQuery({
  queryKey: ['schools-list'],
  queryFn: ({ signal }) => schoolsApi.list({ signal }),
  staleTime: 5 * 60_000,
});

export const useTeacherNorms = (schoolId, teacherId) => useQuery({
  queryKey: ['schools', schoolId, 'teachers', teacherId, 'norms'],
  queryFn: ({ signal }) => schoolsApi.norms(schoolId, teacherId, { signal }),
  enabled: Boolean(schoolId && teacherId),
});

export function useAddTeacher(schoolId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) => schoolsApi.addTeacher(schoolId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schools', schoolId, 'teachers'] });
      qc.invalidateQueries({ queryKey: ['schools-list'] });
    },
  });
}

export const useExportJobs = (params) => useQuery({
  queryKey: ['exports', params],
  queryFn: ({ signal }) => exportsApi.list(params, { signal }),
  placeholderData: keepPreviousData,
  refetchInterval: (q) => (q.state.data?.items.some((j) => j.status === 'running') ? 3000 : false),
});

export function useCreateExport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) => exportsApi.create(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['exports'] }),
  });
}

export const useAdminUsers = (params) => useQuery({
  queryKey: ['admin', 'users', params],
  queryFn: ({ signal }) => adminApi.users(params, { signal }),
  placeholderData: keepPreviousData,
});

export const useAdminDirectory = () => useQuery({
  queryKey: ['admin', 'directory'],
  queryFn: async ({ signal }) => {
    const [schools, groups] = await Promise.all([adminApi.schools({ signal }), adminApi.groups({ signal })]);
    return { schools, groups };
  },
  staleTime: 5 * 60_000,
});

export const useUserAudit = (userId) => useQuery({
  queryKey: ['admin', 'audit', userId],
  queryFn: ({ signal }) => adminApi.audit(userId, { signal }),
  enabled: Boolean(userId),
});

export function useAdminMutations() {
  const qc = useQueryClient();
  const onSuccess = () => qc.invalidateQueries({ queryKey: ['admin'] });
  return {
    setAccess: useMutation({ mutationFn: ({ userId, body }) => adminApi.setAccess(userId, body), onSuccess }),
    block: useMutation({ mutationFn: ({ userId, unblock }) => adminApi.block(userId, unblock), onSuccess }),
    create: useMutation({ mutationFn: (body) => adminApi.create(body), onSuccess }),
  };
}
