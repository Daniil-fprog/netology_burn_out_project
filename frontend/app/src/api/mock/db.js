// Синтетическая «база» для режима заглушек. Поля и коды повторяют модели backend
// (backend/app/models, backend/app/db/seed.py), чтобы переключение на реальный API
// не требовало правок в страницах.
import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';

dayjs.extend(isoWeek);

export const TODAY = dayjs().format('YYYY-MM-DD');

// ТЗ: 1 академический час = 0,75 обычного часа. В БД всё хранится в обычных часах.
export const ACADEMIC_HOUR = 0.75;

// ---------- пользователи и доступ ----------
// Пароль у всех демо-пользователей: demo
export const users = [
  { id: 1, name: 'Белова Ирина В.', login: 'teacher', roles: ['teacher'] },
  { id: 2, name: 'Кузнецов Андрей М.', login: 'director', roles: ['director'] },
  { id: 3, name: 'Лебедева Наталья О.', login: 'head', roles: ['head'] },
  { id: 4, name: 'Морозов Виктор Е.', login: 'group_head', roles: ['group_head'] },
  { id: 5, name: 'Системный администратор', login: 'admin', roles: ['system_admin'] },
].map((u) => ({ ...u, phone: null, is_active: true, created_at: '2026-09-01T09:00:00', updated_at: '2026-09-01T09:00:00' }));

export const schoolGroups = [{ id: 'G1', name: 'Северный округ', school_ids: ['S101', 'S102'] }];

export const schools = [
  { id: 'S101', name: 'МБОУ «Школа № 101 — Демонстрационная»', external_code: 'DEMO-SCHOOL-101', group_id: 'G1' },
  { id: 'S102', name: 'МБОУ «Школа № 102 — Демонстрационная»', external_code: 'DEMO-SCHOOL-102', group_id: 'G1' },
];

// user_school_access + назначения групп
export const schoolAccess = { 1: ['S101'], 2: ['S101'], 3: ['S101', 'S102'], 4: ['S101', 'S102'], 5: [] };

// ---------- справочник видов работ (коды из seed.py) ----------
const wt = (id, code, name, category_group, complexity_weight, requires_comment = false) => ({
  id, code, name, category_group, complexity_weight, requires_comment,
  is_active: true, description: null, archived_at: null, created_at: '2026-09-01T09:00:00', updated_at: '2026-09-01T09:00:00',
});
export const workTypes = [
  wt('WT1', 'lessons', 'Проведение уроков', 'teaching', 0.25),
  wt('WT2', 'substitutions', 'Замены', 'teaching', 0.1),
  wt('WT3', 'preparation', 'Подготовка к уроку', 'teaching_support', 0.15),
  wt('WT4', 'grading', 'Проверка работ', 'teaching_support', 0.12),
  wt('WT5', 'documentation', 'Документация', 'administrative', 0.1),
  wt('WT6', 'parent_communication', 'Общение с родителями', 'communication', 0.14),
  wt('WT7', 'class_management', 'Классное руководство', 'student_support', 0.1),
  wt('WT8', 'meetings_methodology', 'Совещания и методическая работа', 'professional_development', 0.08),
  wt('WT9', 'other', 'Прочее', 'other', 0, true),
];
const WT = Object.fromEntries(workTypes.map((w) => [w.code, w.id]));

// ---------- педагоги и нормы ----------
// contract — уч. ч в неделю по договору, rate — норма за ставку
const teacherSeed = [
  ['T001', 'S101', 'Абрамова Елена С.', 'Математика', 12, 18, false, 0.9, null],
  ['T002', 'S101', 'Белова Ирина В.', 'Русский язык и литература', 18, 18, true, 1.6, 1],
  ['T003', 'S101', 'Волков Дмитрий А.', 'Английский язык', 24, 18, false, 0.8, null],
  ['T004', 'S101', 'Григорьева Анна П.', 'История', 18, 18, true, 1.0, null],
  ['T005', 'S101', 'Дьяченко Олег Н.', 'Физика', 20, 18, false, 1.0, null],
  ['T006', 'S101', 'Ершова Мария К.', 'Начальные классы', 20, 20, true, 1.3, null],
  ['T101', 'S102', 'Жукова Светлана Р.', 'Математика', 22, 18, true, 1.1, null],
  ['T102', 'S102', 'Зайцев Павел И.', 'Информатика', 16, 18, false, 0.7, null],
  ['T103', 'S102', 'Иванова Ольга Д.', 'Русский язык и литература', 20, 18, true, 1.5, null],
];
export const teachers = teacherSeed.map(([id, school_id, full_name, subject, contract, rate, classTeacher, gradingLoad, user_id]) => ({
  id, school_id, external_id: id, full_name, subject, is_active: true, user_id,
  _classTeacher: classTeacher, _gradingLoad: gradingLoad,
}));
export const norms = teacherSeed.map(([id, , , , contract, rate]) => ({
  id: `N-${id}`, teacher_id: id, effective_from: '2026-09-01', effective_to: null,
  contract_teaching_hours_per_week: contract, standard_teaching_hours_per_rate: rate,
  comment: null, plan_source: 'IMPORT_teacher_norms.xlsx', source_import_id: 'I1',
}));

// ---------- план и факт ----------
function mulberry32(seed) {
  return function rand() {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(20261111);
const r2 = (x) => Math.round(x * 100) / 100;

const START = dayjs(TODAY).subtract(5, 'week').startOf('isoWeek');
const END = dayjs(TODAY).endOf('isoWeek');

export const planItems = []; // PlannedWorkItem
export const dailyLogs = []; // DailyWorkLog + entries
export const surveyResponses = [];

let seq = 1;
const nextId = (p) => `${p}${seq++}`;

for (let d = START; !d.isAfter(END); d = d.add(1, 'day')) {
  const dow = d.isoWeekday();
  if (dow > 5) continue;
  const date = d.format('YYYY-MM-DD');
  for (const t of teachers) {
    const n = norms.find((x) => x.teacher_id === t.id);
    const contract = n.contract_teaching_hours_per_week;
    const lessons = Math.floor(contract / 5) + (dow - 1 < contract % 5 ? 1 : 0);
    const plan = [
      ['lessons', r2(lessons * ACADEMIC_HOUR), `${lessons} ур.`],
      ['preparation', r2(lessons * 0.33)],
      ['grading', r2(lessons * 0.22 * t._gradingLoad)],
      ['documentation', 0.35],
      ['parent_communication', 0.1],
    ];
    if (t._classTeacher) plan.push(['class_management', 0.3]);
    if (dow === 1) plan.push(['meetings_methodology', 1.0]);
    const items = plan.map(([code, hours, comment], i) => ({
      id: nextId('P'), plan_version_id: 'PV1', teacher_id: t.id, work_type_id: WT[code], work_date: date,
      day_type: 'Учебный день', subject: code === 'lessons' ? t.subject : null, duration_hours: hours,
      sequence_no: i + 1, comment: comment ?? null,
    }));
    planItems.push(...items);

    if (!d.isBefore(dayjs(TODAY), 'day')) continue;
    if (rand() < 0.08) continue; // нет данных ≠ 0
    const overrun = 1 + t._gradingLoad * 0.15 + (rand() - 0.4) * 0.35;
    const entries = items.map((p) => {
      const isLesson = p.work_type_id === WT.lessons;
      const hours = isLesson ? p.duration_hours : r2(Math.max(0, p.duration_hours * (overrun + (rand() - 0.5) * 0.4)));
      const home = [WT.preparation, WT.grading].includes(p.work_type_id) && rand() < 0.65;
      return { id: nextId('E'), planned_work_item_id: p.id, work_type_id: p.work_type_id, duration_hours: hours, location: home ? 'home' : 'school', comment: null };
    });
    if (rand() < 0.3) {
      const code = ['substitutions', 'parent_communication', 'other'][Math.floor(rand() * 3)];
      entries.push({
        id: nextId('E'), planned_work_item_id: null, work_type_id: WT[code], duration_hours: r2(0.5 + rand()),
        location: 'school', comment: code === 'other' ? 'Школьное мероприятие' : null,
      });
    }
    const daysAgo = dayjs(TODAY).diff(d, 'day');
    const completed = !(daysAgo <= 3 && rand() < 0.5);
    dailyLogs.push({
      id: nextId('L'), teacher_id: t.id, work_date: date, day_type: 'Учебный день',
      status: completed ? 'completed' : 'draft', comment: null,
      completed_at: completed ? d.hour(21).format('YYYY-MM-DDTHH:mm:ss') : null,
      updated_at: d.hour(21).format('YYYY-MM-DDTHH:mm:ss'),
      entries,
    });

    if (rand() < 0.8) {
      const load = entries.reduce((s, e) => s + e.duration_hours, 0);
      const planned = items.reduce((s, p) => s + p.duration_hours, 0);
      const strain = Math.min(1, Math.max(0, (load - planned) / 3 + load / 14));
      const sc = (bias = 0) => Math.min(5, Math.max(1, Math.round(1 + strain * 3.2 + bias + (rand() - 0.5) * 1.4)));
      surveyResponses.push({
        id: nextId('R'), school_id: t.school_id, teacher_id: t.id, survey_code: 'daily_checkin', survey_version: '1.0.0',
        cadence: 'daily', assessment_date: date, period_start: date, period_end: date, comment_reference_date: date,
        status: 'submitted', source: 'web_form', lock_version: 1,
        submitted_at: d.hour(21).minute(30).format('YYYY-MM-DDTHH:mm:ss'),
        answers: {
          fatigue_score: sc(0.3), stress_score: sc(0), workload_perception: sc(0.2),
          emotional_exhaustion_today: sc(-0.3), recovery_capacity: 6 - sc(0), control_over_tasks: 6 - sc(-0.2),
          main_overload_source: t._gradingLoad > 1.2 ? 'grading' : ['teaching', 'documentation', 'communication'][Math.floor(rand() * 3)],
          today_workload_feeling: strain > 0.6
            ? 'Большой объём проверки, после уроков осталось много заданий.'
            : 'Нагрузка ощущалась умеренной, удалось закончить задачи вовремя.',
        },
      });
    }
  }
}

export const imports = [
  { id: 'I3', school_id: 'S101', status: 'completed', mode: 'upsert', original_filename: 'plan_nov_w2.xlsx', created_at: dayjs(TODAY).subtract(3, 'day').hour(10).format('YYYY-MM-DDTHH:mm:ss'), rows_total: 152, rows_inserted: 140, rows_updated: 12, rows_rejected: 0 },
  { id: 'I2', school_id: 'S101', status: 'completed_with_errors', mode: 'insert_only', original_filename: 'plan_nov_w1.xlsx', created_at: dayjs(TODAY).subtract(10, 'day').hour(9).format('YYYY-MM-DDTHH:mm:ss'), rows_total: 132, rows_inserted: 128, rows_updated: 0, rows_rejected: 4 },
  { id: 'I1', school_id: 'S101', status: 'completed', mode: 'insert_only', original_filename: 'norms_2026_27.xlsx', created_at: dayjs(TODAY).subtract(40, 'day').hour(14).format('YYYY-MM-DDTHH:mm:ss'), rows_total: 6, rows_inserted: 6, rows_updated: 0, rows_rejected: 0 },
];
