// Заглушка backend: те же адреса и формат ответов, что в documentation/api.md
import { ApiError } from '../errors';
import * as db from './db';
import surveyCatalog from './surveys.json';

const MANAGERS = ['director', 'head', 'group_head'];
const PLAN_ROLES = MANAGERS;
const FACT_ROLES = ['teacher', 'head', 'group_head'];
const SURVEY_ROLES = FACT_ROLES;
const clone = (x) => structuredClone(x);
const latency = () => new Promise((r) => setTimeout(r, 150 + Math.random() * 250));

function page(items, query) {
  const pageNo = Math.max(1, Number(query.page ?? 1));
  const size = Math.min(200, Math.max(1, Number(query.page_size ?? 50)));
  const start = (pageNo - 1) * size;
  return { page: pageNo, page_size: size, total: items.length, items: items.slice(start, start + size) };
}

function currentUser(token) {
  const id = Number(String(token ?? '').replace('mock-token-', ''));
  const user = db.users.find((u) => u.id === id);
  if (!user) throw new ApiError(401, 'Не авторизован');
  return user;
}

function requireSchool(user, schoolId, roles) {
  if (!user.roles.some((r) => roles.includes(r))) throw new ApiError(403, 'Недостаточно прав');
  if (!(db.schoolAccess[user.id] ?? []).includes(schoolId)) throw new ApiError(403, 'Нет доступа к школе');
}

const ownTeacherId = (user, schoolId) => (user.roles.includes('teacher')
  ? db.teachers.find((t) => t.user_id === user.id && t.school_id === schoolId)?.id ?? null
  : null);

const routes = [
  {
    method: 'POST', path: '/users/login', auth: false,
    handle: ({ body }) => {
      const user = db.users.find((u) => u.login === body?.login);
      if (!user || body?.password !== 'demo') throw new ApiError(401, 'Неверный логин или пароль');
      if (!user.is_active) throw new ApiError(403, 'Вход заблокирован администратором');
      return { access_token: `mock-token-${user.id}`, token_type: 'bearer' };
    },
  },
  {
    method: 'GET', path: '/users/me',
    handle: ({ user }) => {
      const { roles, ...rest } = user;
      return clone(rest);
    },
  },
  {
    method: 'GET', path: '/api/v1/me/access', missing: true,
    handle: ({ user }) => ({
      roles: user.roles,
      schools: (db.schoolAccess[user.id] ?? []).map((id) => {
        const s = db.schools.find((x) => x.id === id);
        return { id: s.id, name: s.name, external_code: s.external_code, teacher_id: ownTeacherId(user, id) };
      }),
    }),
  },
  {
    method: 'GET', path: '/api/v1/work-types',
    handle: ({ query }) => clone(db.workTypes.filter((w) => query.include_archived === 'true' || w.is_active)),
  },
  {
    method: 'GET', path: '/api/v1/schools/:schoolId/teachers',
    handle: ({ user, params, query }) => {
      requireSchool(user, params.schoolId, [...PLAN_ROLES, 'teacher']);
      const own = ownTeacherId(user, params.schoolId);
      const q = (query.q ?? '').trim().toLowerCase(); // поиск по ФИО — в backend нет
      const items = db.teachers
        .filter((t) => t.school_id === params.schoolId)
        .filter((t) => !own || t.id === own)
        .filter((t) => !query.subject || t.subject === query.subject)
        .filter((t) => query.only_active !== 'true' || t.is_active) // в backend нет
        .filter((t) => !q || t.full_name.toLowerCase().includes(q) || t.subject.toLowerCase().includes(q))
        .sort((a, b) => a.external_id.localeCompare(b.external_id))
        .map((t) => {
          const n = db.norms.find((x) => x.teacher_id === t.id && x.effective_to == null);
          return {
            id: t.id, external_id: t.external_id, subject: t.subject, is_active: t.is_active,
            full_name: t.full_name,
            has_account: Boolean(t.user_id), // в backend нет
            current_norm: n && {
              effective_from: n.effective_from,
              contract_teaching_hours_per_week: n.contract_teaching_hours_per_week,
              standard_teaching_hours_per_rate: n.standard_teaching_hours_per_rate,
              rate_fraction: n.contract_teaching_hours_per_week / n.standard_teaching_hours_per_rate,
            },
          };
        });
      return page(items, query);
    },
  },
  {
    method: 'GET', path: '/api/v1/schools/:schoolId/workload/imports',
    handle: ({ user, params, query }) => {
      requireSchool(user, params.schoolId, PLAN_ROLES);
      return page(clone(db.imports.filter((i) => i.school_id === params.schoolId)), query);
    },
  },
  {
    method: 'GET', path: '/api/v1/schools/:schoolId/workload/daily',
    handle: ({ user, params, query }) => {
      requireSchool(user, params.schoolId, [...FACT_ROLES]);
      const own = ownTeacherId(user, params.schoolId);
      const teacherId = own ?? query.teacher_id;
      const ids = new Set(db.teachers.filter((t) => t.school_id === params.schoolId && (!teacherId || t.id === teacherId)).map((t) => t.id));
      const inRange = (d) => (!query.date_from || d >= query.date_from) && (!query.date_to || d <= query.date_to);
      const keys = new Map();
      for (const p of db.planItems) if (ids.has(p.teacher_id) && inRange(p.work_date)) keys.set(`${p.teacher_id}|${p.work_date}`, [p.teacher_id, p.work_date]);
      for (const l of db.dailyLogs) if (ids.has(l.teacher_id) && inRange(l.work_date)) keys.set(`${l.teacher_id}|${l.work_date}`, [l.teacher_id, l.work_date]);
      const rows = [...keys.values()].map(([tid, date]) => dailyRow(tid, date, Boolean(own)));
      rows.sort((a, b) => (query.sort === 'date_asc' ? a.work_date.localeCompare(b.work_date) : b.work_date.localeCompare(a.work_date)));
      return page(rows, query);
    },
  },
  {
    method: 'POST', path: '/api/v1/schools/:schoolId/workload/daily', missing: true,
    handle: ({ user, params, body }) => {
      requireSchool(user, params.schoolId, ['teacher']);
      const own = ownTeacherId(user, params.schoolId);
      if (!own) throw new ApiError(403, 'Нет профиля педагога в школе');
      if (body.work_date > db.TODAY) throw new ApiError(422, 'Нельзя вносить факт за будущую дату');
      if (db.dailyLogs.some((l) => l.teacher_id === own && l.work_date === body.work_date)) throw new ApiError(409, 'Журнал за эту дату уже есть');
      validateEntries(body.entries ?? []);
      const log = {
        id: `L-new-${Date.now()}`, teacher_id: own, work_date: body.work_date, day_type: body.day_type ?? 'Учебный день',
        status: body.status ?? 'draft', comment: body.comment ?? null, entries: [],
      };
      applyLog(log, body, user);
      db.dailyLogs.push(log);
      return dailyRow(own, log.work_date, true);
    },
  },
  {
    method: 'PATCH', path: '/api/v1/schools/:schoolId/workload/daily/:recordId',
    handle: ({ user, params, body }) => {
      requireSchool(user, params.schoolId, ['teacher']);
      const own = ownTeacherId(user, params.schoolId);
      const log = db.dailyLogs.find((l) => l.id === params.recordId);
      if (!log || log.teacher_id !== own) throw new ApiError(404, 'Запись не найдена');
      if (body.entries) validateEntries(body.entries);
      applyLog(log, body, user);
      return dailyRow(own, log.work_date, true);
    },
  },
  {
    method: 'GET', path: '/api/v1/schools/:schoolId/surveys/:code',
    handle: ({ user, params }) => {
      requireSchool(user, params.schoolId, [...SURVEY_ROLES]);
      const s = surveyCatalog.surveys.find((x) => x.code === params.code);
      if (!s) throw new ApiError(404, 'Опрос не найден');
      return clone(s);
    },
  },
  {
    method: 'GET', path: '/api/v1/schools/:schoolId/survey-responses',
    handle: ({ user, params, query }) => {
      requireSchool(user, params.schoolId, [...SURVEY_ROLES]);
      const own = ownTeacherId(user, params.schoolId);
      const items = db.surveyResponses
        .filter((r) => r.school_id === params.schoolId)
        .filter((r) => (own ? r.teacher_id === own : !query.teacher_id || r.teacher_id === query.teacher_id))
        .filter((r) => !query.survey_code || r.survey_code === query.survey_code)
        .filter((r) => !query.status || r.status === query.status)
        .filter((r) => (!query.date_from || r.assessment_date >= query.date_from) && (!query.date_to || r.assessment_date <= query.date_to))
        .sort((a, b) => b.assessment_date.localeCompare(a.assessment_date))
        .map((r) => responseOut(r, r.teacher_id === own));
      return page(items, query);
    },
  },
  {
    method: 'POST', path: '/api/v1/schools/:schoolId/survey-responses',
    handle: ({ user, params, body }) => {
      requireSchool(user, params.schoolId, ['teacher']);
      const own = ownTeacherId(user, params.schoolId);
      if (!own) throw new ApiError(403, 'Нет профиля педагога в школе');
      const survey = surveyCatalog.surveys.find((x) => x.code === body.survey_code);
      if (!survey) throw new ApiError(404, 'Опрос не найден');
      if (body.assessment_date > db.TODAY) throw new ApiError(422, 'Нельзя заполнить опрос за будущую дату');
      const dup = db.surveyResponses.find((r) => r.teacher_id === own && r.survey_code === body.survey_code
        && r.assessment_date === body.assessment_date && r.status !== 'withdrawn');
      if (dup) throw new ApiError(409, 'Ответ за эту дату уже есть');
      validateAnswers(survey, body.answers ?? {}, body.status === 'submitted');
      const r = {
        id: `R-new-${Date.now()}`, school_id: params.schoolId, teacher_id: own, survey_code: survey.code, survey_version: survey.version,
        cadence: survey.cadence, assessment_date: body.assessment_date, period_start: body.period_start, period_end: body.period_end,
        comment_reference_date: body.assessment_date, status: body.status ?? 'draft', source: body.source ?? 'web_form',
        submitted_at: body.status === 'submitted' ? nowIso() : null, lock_version: 1, answers: clone(body.answers ?? {}),
      };
      db.surveyResponses.push(r);
      return responseOut(r, true);
    },
  },
  {
    method: 'PATCH', path: '/api/v1/schools/:schoolId/survey-responses/:responseId',
    handle: ({ user, params, body }) => {
      const r = ownResponse(user, params);
      if (r.status !== 'draft') throw new ApiError(409, 'Изменять можно только черновик');
      const survey = surveyCatalog.surveys.find((x) => x.code === r.survey_code);
      validateAnswers(survey, body.answers ?? {}, false);
      r.answers = clone(body.answers ?? {});
      r.lock_version += 1;
      return responseOut(r, true);
    },
  },
  {
    method: 'POST', path: '/api/v1/schools/:schoolId/survey-responses/:responseId/submit',
    handle: ({ user, params }) => {
      const r = ownResponse(user, params);
      if (r.status !== 'draft') throw new ApiError(409, 'Ответ уже отправлен');
      validateAnswers(surveyCatalog.surveys.find((x) => x.code === r.survey_code), r.answers, true);
      r.status = 'submitted';
      r.submitted_at = nowIso();
      r.lock_version += 1;
      return responseOut(r, true);
    },
  },
  {
    method: 'POST', path: '/api/v1/work-types',
    handle: ({ user, body }) => {
      requireRole(user, WORK_TYPE_EDITORS);
      if (!/^[a-z0-9_-]+$/.test(body.code ?? '')) throw new ApiError(422, 'Код: только латиница в нижнем регистре, цифры, «_» и «-»');
      if (db.workTypes.some((w) => w.code === body.code)) throw new ApiError(409, 'Тип работы с таким кодом уже существует');
      const w = {
        id: `WT-${Date.now()}`, code: body.code, name: body.name, category_group: body.category_group,
        complexity_weight: Number(body.complexity_weight ?? 0), requires_comment: Boolean(body.requires_comment),
        is_active: true, description: body.description ?? null, archived_at: null, created_at: nowIso(), updated_at: nowIso(),
      };
      checkWeight(w.complexity_weight);
      db.workTypes.push(w);
      return clone(w);
    },
  },
  {
    method: 'PATCH', path: '/api/v1/work-types/:id',
    handle: ({ user, params, body }) => {
      requireRole(user, WORK_TYPE_EDITORS);
      const w = db.workTypes.find((x) => x.id === params.id);
      if (!w) throw new ApiError(404, 'Тип работы не найден');
      if (body.complexity_weight !== undefined) checkWeight(Number(body.complexity_weight));
      for (const k of ['name', 'category_group', 'complexity_weight', 'requires_comment', 'is_active', 'description']) {
        if (body[k] !== undefined) w[k] = k === 'complexity_weight' ? Number(body[k]) : body[k];
      }
      if (body.is_active === true) w.archived_at = null;
      w.updated_at = nowIso();
      return clone(w);
    },
  },
  {
    method: 'POST', path: '/api/v1/work-types/:id/archive',
    handle: ({ user, params }) => {
      requireRole(user, WORK_TYPE_EDITORS);
      const w = db.workTypes.find((x) => x.id === params.id);
      if (!w) throw new ApiError(404, 'Тип работы не найден');
      w.is_active = false;
      w.archived_at = nowIso();
      w.updated_at = nowIso();
      return clone(w);
    },
  },
  {
    method: 'GET', path: '/api/v1/dashboard/planned',
    handle: ({ user, query }) => {
      requireSchool(user, query.school_id, PLAN_ROLES);
      if (!query.date_from || !query.date_to || query.date_from > query.date_to) throw new ApiError(422, 'Неверный период');
      const teachers = db.teachers.filter((t) => t.school_id === query.school_id);
      const tIds = new Set(teachers.map((t) => t.id));
      const items = db.planItems.filter((p) => tIds.has(p.teacher_id) && p.work_date >= query.date_from && p.work_date <= query.date_to);
      const teachingIds = new Set(db.workTypes.filter((w) => w.category_group === 'teaching').map((w) => w.id));
      const weekOf = (d) => isoWeekStart(d);
      const agg = (keyFn, filter = () => true) => {
        const m = new Map();
        for (const p of items.filter(filter)) m.set(keyFn(p), (m.get(keyFn(p)) ?? 0) + p.duration_hours);
        return m;
      };
      const teaching = agg((p) => p.teacher_id, (p) => teachingIds.has(p.work_type_id));
      const totals = agg((p) => p.teacher_id);
      const weekly = agg((p) => weekOf(p.work_date));
      const bySubject = agg((p) => p.subject ?? db.teachers.find((t) => t.id === p.teacher_id).subject);
      const values = [...teaching.values()].sort((a, b) => a - b);
      const median = values.length ? (values.length % 2 ? values[(values.length - 1) / 2] : (values[values.length / 2 - 1] + values[values.length / 2]) / 2) : null;
      const r = (x) => Math.round(x * 100) / 100;
      return {
        date_from: query.date_from,
        date_to: query.date_to,
        kpi: {
          planned_teaching_hours: r(values.reduce((s, x) => s + x, 0)),
          teacher_count: totals.size,
          average_teaching_hours: values.length ? r(values.reduce((s, x) => s + x, 0) / values.length) : null,
          median_teaching_hours: median == null ? null : r(median),
        },
        weekly: [...weekly.entries()].sort().map(([week_start, hours]) => ({ week_start, hours: r(hours) })),
        by_subject: [...bySubject.entries()].sort().map(([subject, hours]) => ({ subject, hours: r(hours) })),
        by_school: [{ school: db.schools.find((s) => s.id === query.school_id).name, hours: r([...totals.values()].reduce((s, x) => s + x, 0)) }],
        teachers: [...totals.keys()].sort().map((tid) => {
          const t = db.teachers.find((x) => x.id === tid);
          const n = db.norms.find((x) => x.teacher_id === tid);
          const weeks = new Set(items.filter((p) => p.teacher_id === tid).map((p) => weekOf(p.work_date))).size;
          const expected = n ? n.contract_teaching_hours_per_week * weeks : null;
          return {
            teacher_id: tid, full_name: t.full_name, subject: t.subject,
            planned_hours: r(totals.get(tid)), planned_teaching_hours: r(teaching.get(tid) ?? 0),
            individual_norm_hours: expected,
            deviation_from_norm_hours: expected == null ? null : r((teaching.get(tid) ?? 0) - expected),
          };
        }),
      };
    },
  },
  // нет в backend: построчный список плана
  {
    method: 'GET', path: '/api/v1/schools/:schoolId/workload/plan-items', missing: true,
    handle: ({ user, params, query }) => {
      requireSchool(user, params.schoolId, PLAN_ROLES);
      const tIds = new Set(db.teachers.filter((t) => t.school_id === params.schoolId).map((t) => t.id));
      const items = db.planItems
        .filter((p) => tIds.has(p.teacher_id))
        .filter((p) => !query.teacher_id || p.teacher_id === query.teacher_id)
        .filter((p) => !query.work_type_id || p.work_type_id === query.work_type_id)
        .filter((p) => (!query.date_from || p.work_date >= query.date_from) && (!query.date_to || p.work_date <= query.date_to))
        .sort((a, b) => a.work_date.localeCompare(b.work_date) || a.teacher_id.localeCompare(b.teacher_id) || a.sequence_no - b.sequence_no)
        .map((p) => ({ ...clone(p), plan_version: 1, source_import_filename: 'plan_nov_w2.xlsx' }));
      return page(items, query);
    },
  },
  {
    method: 'POST', path: '/api/v1/schools/:schoolId/workload/imports/validate',
    handle: ({ user, params, body }) => {
      requireSchool(user, params.schoolId, PLAN_ROLES);
      return mockValidation(body);
    },
  },
  {
    method: 'POST', path: '/api/v1/schools/:schoolId/workload/imports',
    handle: ({ user, params, body }) => {
      requireSchool(user, params.schoolId, PLAN_ROLES);
      const report = mockValidation(body);
      if (!report.valid) throw new ApiError(422, 'Файл содержит ошибки', report);
      const item = {
        id: `I-${Date.now()}`, school_id: params.schoolId, original_filename: body.get('file').name, sha256: 'mock',
        status: 'completed', mode: body.get('mode') ?? 'insert_only', effective_from: body.get('effective_from'),
        rows_total: report.summary.to_create, rows_created: report.summary.to_create, rows_updated: 0, rows_skipped: 0,
        validation_report: report, imported_at: nowIso(), created_by_name: user.name,
      };
      db.imports.unshift(item);
      return clone(item);
    },
  },
  ...['/api/v1/schools/:schoolId/workload/template', '/api/v1/schools/:schoolId/workload/exports', '/api/v1/schools/:schoolId/workload/imports/:importId/file'].map((path) => ({
    method: 'GET', path,
    handle: () => { throw new ApiError(501, 'В режиме заглушек файлы не формируются — нужен настоящий backend'); },
  })),
];

routes.push(
  {
    method: 'GET', path: '/api/v1/schools', missing: true,
    handle: ({ user }) => (db.schoolAccess[user.id] ?? []).map((id) => {
      const s = db.schools.find((x) => x.id === id);
      const ts = db.teachers.filter((t) => t.school_id === id);
      const director = db.users.find((u) => u.roles.includes('director') && (db.schoolAccess[u.id] ?? []).includes(id));
      return {
        id: s.id, name: s.name, external_code: s.external_code,
        group: db.schoolGroups.find((g) => g.id === s.group_id)?.name ?? null,
        teacher_count: ts.filter((t) => t.is_active).length,
        linked_accounts: ts.filter((t) => t.user_id).length,
        director_name: director?.name ?? null,
      };
    }),
  },
  {
    method: 'GET', path: '/api/v1/schools/:schoolId/teachers/:teacherId/norms',
    handle: ({ user, params }) => {
      requireSchool(user, params.schoolId, [...PLAN_ROLES, 'teacher']);
      const own = ownTeacherId(user, params.schoolId);
      if (own && own !== params.teacherId) throw new ApiError(403, 'Недостаточно прав');
      return clone(db.norms.filter((n) => n.teacher_id === params.teacherId))
        .sort((a, b) => b.effective_from.localeCompare(a.effective_from));
    },
  },
  {
    method: 'POST', path: '/api/v1/schools/:schoolId/teachers',
    handle: ({ user, params, body }) => {
      requireSchool(user, params.schoolId, PLAN_ROLES);
      if (!body.external_id?.trim() || !body.full_name?.trim() || !body.subject?.trim()) throw new ApiError(422, 'Заполните код, ФИО и предмет');
      if (db.teachers.some((t) => t.school_id === params.schoolId && t.external_id === body.external_id)) throw new ApiError(409, 'Педагог с таким кодом уже есть в школе');
      const t = { id: `T-${Date.now()}`, school_id: params.schoolId, external_id: body.external_id.trim(), full_name: body.full_name.trim(), subject: body.subject.trim(), is_active: true, user_id: body.user_id ?? null };
      db.teachers.push(t);
      return { id: t.id, external_id: t.external_id, subject: t.subject, is_active: true };
    },
  },
  {
    method: 'GET', path: '/api/v1/exports', missing: true,
    handle: ({ user, query }) => {
      tickJobs();
      return page(clone(db.exportJobs.filter((j) => j.user_id === user.id)).sort((a, b) => b.created_at.localeCompare(a.created_at)), query);
    },
  },
  {
    method: 'POST', path: '/api/v1/exports', missing: true,
    handle: ({ user, body }) => {
      const allowed = REPORT_ROLES[body.report];
      if (!allowed) throw new ApiError(422, 'Неизвестный отчёт');
      if (!user.roles.some((r) => allowed.includes(r))) throw new ApiError(403, 'Этот отчёт недоступен для вашей роли');
      for (const sid of body.school_ids ?? []) requireSchool(user, sid, allowed);
      if (!body.date_from || !body.date_to || body.date_from > body.date_to) throw new ApiError(422, 'Неверный период');
      const job = {
        id: `X-${Date.now()}`, user_id: user.id, report: body.report,
        params: { school_ids: body.school_ids, teacher_id: body.teacher_id ?? null, date_from: body.date_from, date_to: body.date_to, format: body.format },
        status: 'running', created_at: nowIso(), expires_at: null, _readyAt: Date.now() + 4000,
      };
      db.exportJobs.push(job);
      return clone(job);
    },
  },
  {
    method: 'GET', path: '/api/v1/exports/:id/file', missing: true,
    handle: () => { throw new ApiError(501, 'В режиме заглушек файлы не формируются — нужен настоящий backend'); },
  },
  {
    method: 'GET', path: '/api/v1/admin/users', missing: true,
    handle: ({ user, query }) => {
      requireRole(user, ['system_admin']);
      const q = (query.q ?? '').trim().toLowerCase();
      const items = db.users
        .filter((u) => !q || u.name.toLowerCase().includes(q) || u.login.toLowerCase().includes(q))
        .filter((u) => !query.role || u.roles.includes(query.role))
        .filter((u) => !query.status || (query.status === 'active' ? u.is_active : !u.is_active))
        .map(adminUserOut);
      return page(items, query);
    },
  },
  {
    method: 'GET', path: '/api/v1/school-groups', missing: true,
    handle: ({ user }) => {
      requireRole(user, ['system_admin']);
      return clone(db.schoolGroups);
    },
  },
  {
    method: 'GET', path: '/api/v1/admin/schools', missing: true,
    handle: ({ user }) => {
      requireRole(user, ['system_admin']);
      return db.schools.map((s) => ({
        id: s.id, name: s.name,
        teachers: db.teachers.filter((t) => t.school_id === s.id).map((t) => ({ id: t.id, full_name: t.full_name, user_id: t.user_id })),
      }));
    },
  },
  {
    method: 'PUT', path: '/api/v1/admin/users/:id/access', missing: true,
    handle: ({ user, params, body }) => {
      requireRole(user, ['system_admin']);
      const u = db.users.find((x) => x.id === Number(params.id));
      if (!u) throw new ApiError(404, 'Пользователь не найден');
      const role = body.role;
      if (!['teacher', 'director', 'head', 'group_head', 'system_admin'].includes(role)) throw new ApiError(422, 'Неизвестная роль');
      let schools = [];
      if (role === 'director' || role === 'teacher') {
        if ((body.school_ids ?? []).length !== 1) throw new ApiError(422, 'Нужна ровно одна школа');
        schools = body.school_ids;
      } else if (role === 'head') {
        if (!(body.school_ids ?? []).length) throw new ApiError(422, 'Выберите хотя бы одну школу');
        schools = body.school_ids;
      } else if (role === 'group_head') {
        if (!(body.group_ids ?? []).length) throw new ApiError(422, 'Выберите хотя бы одну группу');
        schools = db.schoolGroups.filter((g) => body.group_ids.includes(g.id)).flatMap((g) => g.school_ids);
      }
      if (role === 'teacher') {
        const t = db.teachers.find((x) => x.id === body.teacher_id && x.school_id === schools[0]);
        if (!t) throw new ApiError(422, 'Выберите карточку педагога в этой школе');
        if (t.user_id && t.user_id !== u.id) throw new ApiError(409, 'Карточка уже связана с другой учётной записью');
        db.teachers.forEach((x) => { if (x.user_id === u.id) x.user_id = null; });
        t.user_id = u.id;
      } else {
        db.teachers.forEach((x) => { if (x.user_id === u.id) x.user_id = null; });
      }
      const before = adminUserOut(u);
      u.roles = [role];
      db.schoolAccess[u.id] = [...new Set(schools)];
      db.groupAccess[u.id] = role === 'group_head' ? body.group_ids : [];
      u.updated_at = nowIso();
      const after = adminUserOut(u);
      db.accessAudit.push({ id: `A-${Date.now()}`, user_id: u.id, at: nowIso(), actor: user.name, text: `роль «${ROLE_RU[role]}», область: ${after.scope_label}${before.role !== role ? ` (была «${ROLE_RU[before.role] ?? '—'}»)` : ''}` });
      return after;
    },
  },
  {
    method: 'POST', path: '/api/v1/admin/users/:id/block', missing: true,
    handle: ({ user, params, body }) => {
      requireRole(user, ['system_admin']);
      const u = db.users.find((x) => x.id === Number(params.id));
      if (!u) throw new ApiError(404, 'Пользователь не найден');
      if (u.id === user.id) throw new ApiError(422, 'Нельзя заблокировать себя');
      u.is_active = Boolean(body.unblock);
      db.accessAudit.push({ id: `A-${Date.now()}`, user_id: u.id, at: nowIso(), actor: user.name, text: u.is_active ? 'вход разблокирован' : 'вход заблокирован' });
      return adminUserOut(u);
    },
  },
  {
    method: 'POST', path: '/api/v1/admin/users', missing: true,
    handle: ({ user, body }) => {
      requireRole(user, ['system_admin']);
      if (!body.name?.trim() || !body.login?.trim()) throw new ApiError(422, 'Укажите имя и логин');
      if (db.users.some((u) => u.login === body.login.trim())) throw new ApiError(409, 'Логин занят');
      const u = { id: Math.max(...db.users.map((x) => x.id)) + 1, name: body.name.trim(), login: body.login.trim(), roles: [], phone: null, is_active: true, created_at: nowIso(), updated_at: nowIso() };
      db.users.push(u);
      db.schoolAccess[u.id] = [];
      db.accessAudit.push({ id: `A-${Date.now()}`, user_id: u.id, at: nowIso(), actor: user.name, text: 'учётная запись создана' });
      return adminUserOut(u);
    },
  },
  {
    method: 'GET', path: '/api/v1/admin/users/:id/audit', missing: true,
    handle: ({ user, params }) => {
      requireRole(user, ['system_admin']);
      return clone(db.accessAudit.filter((a) => a.user_id === Number(params.id))).sort((a, b) => b.at.localeCompare(a.at));
    },
  },
);

const ROLE_RU = { teacher: 'Преподаватель', director: 'Директор', head: 'Глава', group_head: 'Глава группы', system_admin: 'Администратор' };
const REPORT_ROLES = {
  plan: ['teacher', 'director', 'head', 'group_head'],
  plan_vs_fact: ['teacher', 'head', 'group_head'],
  summary: ['head', 'group_head'],
  surveys: ['teacher', 'head', 'group_head'],
  imports: ['director', 'head', 'group_head'],
  audit: ['head', 'group_head'],
  ml_dataset: ['head', 'group_head'],
};

function tickJobs() {
  const now = Date.now();
  for (const j of db.exportJobs) {
    if (j.status === 'running' && j._readyAt <= now) {
      j.status = 'ready';
      const d = new Date(now + 7 * 864e5);
      j.expires_at = d.toISOString().slice(0, 19);
    }
  }
}

function adminUserOut(u) {
  const role = u.roles[0] ?? null;
  const schoolIds = db.schoolAccess[u.id] ?? [];
  const groupIds = db.groupAccess[u.id] ?? [];
  const teacher = db.teachers.find((t) => t.user_id === u.id) ?? null;
  const schoolName = (id) => db.schools.find((s) => s.id === id)?.name.replace(/^МБОУ «|»$/g, '').replace(/ — .*/, '') ?? id;
  const scope = role === 'group_head'
    ? db.schoolGroups.filter((g) => groupIds.includes(g.id)).map((g) => g.name).join(', ')
    : schoolIds.map(schoolName).join(', ');
  return {
    id: u.id, name: u.name, login: u.login, is_active: u.is_active, role,
    school_ids: schoolIds, group_ids: groupIds,
    teacher: teacher ? { id: teacher.id, full_name: teacher.full_name, school_id: teacher.school_id } : null,
    scope_label: scope || '—',
    updated_at: u.updated_at,
  };
}

const WORK_TYPE_EDITORS = ['head', 'group_head', 'system_admin'];
function requireRole(user, roles) {
  if (!user.roles.some((r) => roles.includes(r))) throw new ApiError(403, 'Недостаточно прав');
}
function checkWeight(v) {
  if (!(v >= 0 && v <= 1)) throw new ApiError(422, 'Коэффициент сложности должен быть от 0 до 1');
}
function isoWeekStart(date) {
  const d = new Date(`${date}T00:00:00`);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
function mockValidation(body) {
  const file = body?.get?.('file');
  if (!file) throw new ApiError(422, 'Файл не передан');
  if (!/\.xlsx$/i.test(file.name)) throw new ApiError(422, 'Нужен файл .xlsx');
  const withErrors = /error|ошиб/i.test(file.name);
  return {
    valid: !withErrors,
    template_version: '1.0',
    summary: { teachers: 6, norms: 6, daily_plans: 145, daily_actuals: 0, to_create: withErrors ? 142 : 145, to_update: 0, to_skip: 0 },
    errors: withErrors ? [
      { sheet: 'План_дня', row: 17, field: 'external_id', message: 'Учитель не найден в этой школе' },
      { sheet: 'План_дня', row: 58, field: 'row', message: 'Некорректная дата: 31.11.2026' },
      { sheet: 'План_дня', row: 96, field: 'row', message: 'Время не может быть отрицательным' },
    ] : [],
    warnings: [{ sheet: 'Учителя_нормы', row: 5, field: 'effective_from', message: `Дата действия ${body.get('effective_from')} взята из параметра импорта` }],
  };
}

const WT_BY_ID = Object.fromEntries(db.workTypes.map((w) => [w.id, w]));
const sumH = (arr) => Math.round(arr.reduce((s, x) => s + Number(x.duration_hours || 0), 0) * 100) / 100;
const nowIso = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
};
const byCode = (items) => Object.fromEntries(db.workTypes.map((w) => [w.code, sumH(items.filter((x) => x.work_type_id === w.id))]));

// Дополнительно (в backend нет): plan.items и actual.entries — построчные данные для формы учителя.
function dailyRow(teacherId, date, isOwner) {
  const teacher = db.teachers.find((t) => t.id === teacherId);
  const items = db.planItems.filter((p) => p.teacher_id === teacherId && p.work_date === date).sort((a, b) => a.sequence_no - b.sequence_no);
  const log = db.dailyLogs.find((l) => l.teacher_id === teacherId && l.work_date === date) ?? null;
  const ptotal = items.length ? sumH(items) : null;
  const atotal = log ? sumH(log.entries) : null;
  const home = log ? sumH(log.entries.filter((e) => e.location === 'home')) : 0;
  const school = log ? sumH(log.entries.filter((e) => e.location === 'school')) : 0;
  const d = new Date(`${date}T00:00:00`);
  const weekStart = new Date(d);
  weekStart.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return {
    teacher_id: teacherId, external_teacher_id: teacher.external_id, work_date: date,
    day_type: log?.day_type ?? items[0]?.day_type ?? 'Учебный день',
    plan: items.length ? {
      total_hours: ptotal, total_complete: true,
      ...Object.fromEntries(Object.entries(byCode(items)).map(([c, v]) => [`planned_${c}_hours`, v])),
      items: clone(items), // нет в backend
    } : null,
    actual: log ? {
      id: log.id, status: log.status, total_hours: atotal, total_complete: log.status === 'completed',
      ...Object.fromEntries(Object.entries(byCode(log.entries)).map(([c, v]) => [`actual_${c}_hours`, v])),
      at_school_hours: school, at_home_hours: home,
      comment: isOwner ? log.comment : undefined,
      updated_at: log.updated_at, // нет в backend (нужно для «Изменено …» и If-Match)
      entries: clone(log.entries).map((e) => (isOwner ? e : { ...e, comment: undefined })), // нет в backend
    } : null,
    metrics: {
      deviation_hours: atotal != null && ptotal != null ? Math.round((atotal - ptotal) * 100) / 100 : null,
      actual_to_plan_ratio: atotal != null && ptotal ? atotal / ptotal : null,
      at_home_share: atotal ? home / atotal : null,
      week_start: `${weekStart.getFullYear()}-${String(weekStart.getMonth() + 1).padStart(2, '0')}-${String(weekStart.getDate()).padStart(2, '0')}`,
    },
  };
}

function validateEntries(entries) {
  let total = 0;
  for (const e of entries) {
    const w = WT_BY_ID[e.work_type_id];
    if (!w || !w.is_active) throw new ApiError(422, 'Неизвестный или архивный тип работы');
    if (!(Number(e.duration_hours) > 0)) throw new ApiError(422, 'Длительность должна быть больше 0');
    if (Number(e.duration_hours) > 24) throw new ApiError(422, 'Одна запись не может быть больше 24 ч');
    if (w.requires_comment && !e.comment?.trim()) throw new ApiError(422, `Для «${w.name}» нужен комментарий`);
    total += Number(e.duration_hours);
  }
  if (total > 24) throw new ApiError(422, 'Сумма за день больше 24 ч');
}

function applyLog(log, body, user) {
  if (body.day_type !== undefined) log.day_type = body.day_type;
  if (body.comment !== undefined) log.comment = body.comment;
  if (body.status !== undefined) {
    log.status = body.status;
    log.completed_at = body.status === 'completed' ? nowIso() : null;
  }
  if (body.entries) {
    log.entries = body.entries.map((e, i) => ({
      id: `E-${log.id}-${i}-${Date.now()}`, planned_work_item_id: e.planned_work_item_id ?? null, work_type_id: e.work_type_id,
      duration_hours: Number(e.duration_hours), location: e.location, comment: e.comment ?? null, created_by: user.id,
    }));
  }
  log.updated_at = nowIso();
}

function responseOut(r, includeComments) {
  const survey = surveyCatalog.surveys.find((x) => x.code === r.survey_code);
  const textIds = new Set(survey.questions.filter((q) => q.type === 'long_text').map((q) => q.id));
  const answers = Object.fromEntries(Object.entries(r.answers).filter(([k]) => includeComments || !textIds.has(k)));
  return { ...clone(r), answers };
}

function ownResponse(user, params) {
  requireSchool(user, params.schoolId, ['teacher']);
  const own = ownTeacherId(user, params.schoolId);
  const r = db.surveyResponses.find((x) => x.id === params.responseId && x.school_id === params.schoolId);
  if (!r || r.teacher_id !== own) throw new ApiError(404, 'Ответ не найден');
  return r;
}

function validateAnswers(survey, answers, submitted) {
  const byId = Object.fromEntries(survey.questions.map((q) => [q.id, q]));
  const unknown = Object.keys(answers).filter((k) => !byId[k]);
  if (unknown.length) throw new ApiError(422, `Неизвестные question_code: ${unknown.join(', ')}`);
  if (submitted) {
    const missing = survey.questions.filter((q) => q.required && (answers[q.id] === undefined || answers[q.id] === '')).map((q) => q.title);
    if (missing.length) throw new ApiError(422, `Нет обязательных ответов: ${missing.join('; ')}`);
  }
  for (const [k, v] of Object.entries(answers)) {
    const q = byId[k];
    if (q.type === 'integer_scale' && (!Number.isInteger(v) || v < (q.min ?? 1) || v > (q.max ?? 5))) throw new ApiError(422, `${q.title}: значение вне шкалы`);
    if (q.type === 'single_choice' && !q.options.some((o) => o.value === v)) throw new ApiError(422, `${q.title}: недопустимый вариант`);
    if (q.type === 'long_text' && (typeof v !== 'string' || v.trim().length > (q.max_length ?? 3000))) throw new ApiError(422, `${q.title}: неверная длина текста`);
  }
}

export const missingEndpoints = () => routes.filter((r) => r.missing).map((r) => `${r.method} ${r.path}`);

function match(pattern, path) {
  const p = pattern.split('/');
  const a = path.split('/');
  if (p.length !== a.length) return null;
  const params = {};
  for (let i = 0; i < p.length; i += 1) {
    if (p[i].startsWith(':')) params[p[i].slice(1)] = decodeURIComponent(a[i]);
    else if (p[i] !== a[i]) return null;
  }
  return params;
}

export async function mockFetch({ method, path, query = {}, body, token }) {
  await latency();
  const cleanPath = path.replace(/\/+$/, '') || '/';
  for (const route of routes) {
    if (route.method !== method) continue;
    const params = match(route.path, cleanPath);
    if (!params) continue;
    const user = route.auth === false ? null : currentUser(token);
    return route.handle({ user, params, query, body });
  }
  throw new ApiError(404, `Заглушка не реализована: ${method} ${cleanPath}`);
}
