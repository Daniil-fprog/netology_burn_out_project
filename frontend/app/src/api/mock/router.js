// Заглушка сервера: отвечает на те же METHOD + путь, что backend (documentation/api.md),
// и в том же формате ответов. Маршруты с пометкой `missing` в backend пока нет:
// это предложения к API, их список — в MISSING_ENDPOINTS.
import { ApiError } from '../errors';
import * as db from './db';
import surveyCatalog from './surveys.json';

const MANAGERS = ['director', 'head', 'group_head'];
const PLAN_ROLES = MANAGERS;
// директору факт и опросы недоступны (ТЗ, матрица доступа)
const FACT_ROLES = ['teacher', 'head', 'group_head'];
const SURVEY_ROLES = FACT_ROLES;
const clone = (x) => structuredClone(x);
const latency = () => new Promise((r) => setTimeout(r, 150 + Math.random() * 250));

// Формат пагинации backend: { page, page_size, total, items }
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
    // Роли, доступные школы и связь с педагогом. В backend /users/me этого не отдаёт.
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
        .filter((t) => !q || t.full_name.toLowerCase().includes(q) || t.subject.toLowerCase().includes(q))
        .sort((a, b) => a.external_id.localeCompare(b.external_id))
        .map((t) => {
          const n = db.norms.find((x) => x.teacher_id === t.id && x.effective_to == null);
          return {
            id: t.id, external_id: t.external_id, subject: t.subject, is_active: t.is_active,
            full_name: t.full_name, // в ответе backend сейчас нет ФИО
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
  // ---------- нагрузка по дням ----------
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
    // Создание дневного журнала, если его ещё нет (например, работа в выходной без плана).
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
  // ---------- опросы ----------
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
];

// ---------- помощники нагрузки ----------
const WT_BY_ID = Object.fromEntries(db.workTypes.map((w) => [w.id, w]));
const sumH = (arr) => Math.round(arr.reduce((s, x) => s + Number(x.duration_hours || 0), 0) * 100) / 100;
// локальное время без зоны — как в остальных моковых датах
const nowIso = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
};
const byCode = (items) => Object.fromEntries(db.workTypes.map((w) => [w.code, sumH(items.filter((x) => x.work_type_id === w.id))]));

// Та же форма, что daily_dict в backend/app/services/workload_service.py.
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

// ---------- помощники опросов ----------
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

// Те же проверки, что validate_answers в backend/app/services/survey_service.py
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

export const MISSING_ENDPOINTS = routes.filter((r) => r.missing).map((r) => `${r.method} ${r.path}`);

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
