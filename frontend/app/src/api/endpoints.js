// Функции = эндпоинты из documentation/api.md. Имена параметров как у backend.
import { request } from './http';

export const authApi = {
  login: (login, password) => request('POST', '/users/login', { body: { login, password } }),
  me: (opts) => request('GET', '/users/me', opts),
  // нет в backend: роли, школы и teacher_id текущего пользователя
  access: (opts) => request('GET', '/api/v1/me/access', opts),
};

export const workTypesApi = {
  list: ({ includeArchived = false } = {}, opts) => request('GET', '/api/v1/work-types', { ...opts, query: { include_archived: includeArchived } }),
};

export const teachersApi = {
  // q — поиск по ФИО/предмету, в backend пока нет (только subject)
  list: (schoolId, { subject, q, page = 1, pageSize = 20 } = {}, opts) => request('GET', `/api/v1/schools/${schoolId}/teachers`, {
    ...opts, query: { subject, q, page, page_size: pageSize },
  }),
};

export const importsApi = {
  list: (schoolId, { page = 1, pageSize = 20 } = {}, opts) => request('GET', `/api/v1/schools/${schoolId}/workload/imports`, {
    ...opts, query: { page, page_size: pageSize },
  }),
};

export const workloadApi = {
  daily: (schoolId, { teacherId, dateFrom, dateTo, sort, page = 1, pageSize = 50 } = {}, opts) => request('GET', `/api/v1/schools/${schoolId}/workload/daily`, {
    ...opts, query: { teacher_id: teacherId, date_from: dateFrom, date_to: dateTo, sort, page, page_size: pageSize },
  }),
  // нет в backend: создать журнал за день, если его ещё нет
  createDay: (schoolId, body) => request('POST', `/api/v1/schools/${schoolId}/workload/daily`, { body }),
  patchDay: (schoolId, recordId, body) => request('PATCH', `/api/v1/schools/${schoolId}/workload/daily/${recordId}`, { body }),
};

export const surveysApi = {
  get: (schoolId, code, opts) => request('GET', `/api/v1/schools/${schoolId}/surveys/${code}`, opts),
  responses: (schoolId, { surveyCode, status, dateFrom, dateTo, page = 1, pageSize = 20 } = {}, opts) => request('GET', `/api/v1/schools/${schoolId}/survey-responses`, {
    ...opts, query: { survey_code: surveyCode, status, date_from: dateFrom, date_to: dateTo, page, page_size: pageSize },
  }),
  create: (schoolId, body) => request('POST', `/api/v1/schools/${schoolId}/survey-responses`, { body }),
  patchDraft: (schoolId, responseId, answers) => request('PATCH', `/api/v1/schools/${schoolId}/survey-responses/${responseId}`, { body: { answers } }),
  submit: (schoolId, responseId) => request('POST', `/api/v1/schools/${schoolId}/survey-responses/${responseId}/submit`),
};
