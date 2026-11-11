// Хуки чтения данных. Ключи запросов собраны в одном месте, чтобы инвалидация
// после изменений была предсказуемой.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  importsApi, surveysApi, teachersApi, workloadApi, workTypesApi,
} from './endpoints';

export const qk = {
  workTypes: (includeArchived) => ['work-types', { includeArchived }],
  teachers: (schoolId, params) => ['schools', schoolId, 'teachers', params],
  imports: (schoolId, params) => ['schools', schoolId, 'imports', params],
  daily: (schoolId, params) => ['schools', schoolId, 'daily', params],
  survey: (schoolId, code) => ['schools', schoolId, 'surveys', code],
  surveyResponses: (schoolId, params) => ['schools', schoolId, 'survey-responses', params],
};

// Справочник меняется редко — держим дольше.
export const useWorkTypes = ({ includeArchived = false } = {}) => useQuery({
  queryKey: qk.workTypes(includeArchived),
  queryFn: ({ signal }) => workTypesApi.list({ includeArchived }, { signal }),
  staleTime: 10 * 60_000,
});

// Постраничные списки: при смене страницы показываем прошлую, пока грузится новая.
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

// ---------- нагрузка ----------
// Неделя целиком одним запросом: из него и полоска статусов, и выбранный день.
export const useDailyRange = (schoolId, { dateFrom, dateTo, teacherId }) => useQuery({
  queryKey: qk.daily(schoolId, { dateFrom, dateTo, teacherId }),
  queryFn: ({ signal }) => workloadApi.daily(schoolId, { dateFrom, dateTo, teacherId, sort: 'date_asc', pageSize: 31 }, { signal }),
  enabled: Boolean(schoolId),
  placeholderData: keepPreviousData,
  staleTime: 30_000,
});

/** Сохранение дня: есть журнал — PATCH, нет — создание. */
export function useSaveDay(schoolId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ recordId, body }) => (recordId
      ? workloadApi.patchDay(schoolId, recordId, body)
      : workloadApi.createDay(schoolId, body)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schools', schoolId, 'daily'] }),
  });
}

// ---------- опросы ----------
export const useSurvey = (schoolId, code) => useQuery({
  queryKey: qk.survey(schoolId, code),
  queryFn: ({ signal }) => surveysApi.get(schoolId, code, { signal }),
  enabled: Boolean(schoolId && code),
  staleTime: 60 * 60_000,
});

export const useSurveyResponses = (schoolId, params) => useQuery({
  queryKey: qk.surveyResponses(schoolId, params),
  queryFn: ({ signal }) => surveysApi.responses(schoolId, params, { signal }),
  enabled: Boolean(schoolId),
  placeholderData: keepPreviousData,
});

/** Черновик или отправка: создаёт ответ, если его ещё нет, иначе обновляет черновик и (при submit) отправляет. */
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
