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
  list: (schoolId, { subject, q, onlyActive, page = 1, pageSize = 20 } = {}, opts) => request('GET', `/api/v1/schools/${schoolId}/teachers`, {
    ...opts, query: { subject, q, only_active: onlyActive, page, page_size: pageSize },
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
  responses: (schoolId, { teacherId, surveyCode, status, dateFrom, dateTo, page = 1, pageSize = 20 } = {}, opts) => request('GET', `/api/v1/schools/${schoolId}/survey-responses`, {
    ...opts, query: { teacher_id: teacherId, survey_code: surveyCode, status, date_from: dateFrom, date_to: dateTo, page, page_size: pageSize },
  }),
  create: (schoolId, body) => request('POST', `/api/v1/schools/${schoolId}/survey-responses`, { body }),
  patchDraft: (schoolId, responseId, answers) => request('PATCH', `/api/v1/schools/${schoolId}/survey-responses/${responseId}`, { body: { answers } }),
  submit: (schoolId, responseId) => request('POST', `/api/v1/schools/${schoolId}/survey-responses/${responseId}/submit`),
};

export const workTypesAdminApi = {
  create: (body) => request('POST', '/api/v1/work-types', { body }),
  update: (id, body) => request('PATCH', `/api/v1/work-types/${id}`, { body }),
  archive: (id) => request('POST', `/api/v1/work-types/${id}/archive`),
};

export const dashboardApi = {
  planned: (schoolId, { dateFrom, dateTo }, opts) => request('GET', '/api/v1/dashboard/planned', {
    ...opts, query: { school_id: schoolId, date_from: dateFrom, date_to: dateTo },
  }),
};

export const plansApi = {
  // нет в backend: построчный список плановых работ
  items: (schoolId, { teacherId, workTypeId, dateFrom, dateTo, page = 1, pageSize = 20 } = {}, opts) => request('GET', `/api/v1/schools/${schoolId}/workload/plan-items`, {
    ...opts, query: { teacher_id: teacherId, work_type_id: workTypeId, date_from: dateFrom, date_to: dateTo, page, page_size: pageSize },
  }),
  validate: (schoolId, form) => request('POST', `/api/v1/schools/${schoolId}/workload/imports/validate`, { body: form }),
  import: (schoolId, form) => request('POST', `/api/v1/schools/${schoolId}/workload/imports`, { body: form }),
};

export const filesApi = {
  template: (schoolId) => request('GET', `/api/v1/schools/${schoolId}/workload/template`),
  export: (schoolId, { dateFrom, dateTo, teacherId, report } = {}) => request('GET', `/api/v1/schools/${schoolId}/workload/exports`, {
    query: { date_from: dateFrom, date_to: dateTo, teacher_id: teacherId, report },
  }),
  importFile: (schoolId, importId) => request('GET', `/api/v1/schools/${schoolId}/workload/imports/${importId}/file`),
};

export const schoolsApi = {
  // нет в backend: школы, доступные пользователю, со сводкой
  list: (opts) => request('GET', '/api/v1/schools', opts),
  norms: (schoolId, teacherId, opts) => request('GET', `/api/v1/schools/${schoolId}/teachers/${teacherId}/norms`, opts),
  addTeacher: (schoolId, body) => request('POST', `/api/v1/schools/${schoolId}/teachers`, { body }),
};

// нет в backend: очередь выгрузок (export_jobs из ТЗ)
export const exportsApi = {
  list: ({ page = 1, pageSize = 10 } = {}, opts) => request('GET', '/api/v1/exports', { ...opts, query: { page, page_size: pageSize } }),
  create: (body) => request('POST', '/api/v1/exports', { body }),
  file: (id) => request('GET', `/api/v1/exports/${id}/file`),
};

// нет в backend: управление пользователями и правами
export const adminApi = {
  users: ({ q, role, status, page = 1, pageSize = 20 } = {}, opts) => request('GET', '/api/v1/admin/users', {
    ...opts, query: { q, role, status, page, page_size: pageSize },
  }),
  schools: (opts) => request('GET', '/api/v1/admin/schools', opts),
  groups: (opts) => request('GET', '/api/v1/school-groups', opts),
  setAccess: (userId, body) => request('PUT', `/api/v1/admin/users/${userId}/access`, { body }),
  block: (userId, unblock = false) => request('POST', `/api/v1/admin/users/${userId}/block`, { body: { unblock } }),
  create: (body) => request('POST', '/api/v1/admin/users', { body }),
  audit: (userId, opts) => request('GET', `/api/v1/admin/users/${userId}/audit`, opts),
};
