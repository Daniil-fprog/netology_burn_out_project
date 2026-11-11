import { useEffect, useMemo, useState } from 'react';
import dayjs from 'dayjs';
import {
  App, Button, Card, DatePicker, Segmented, Select, Tag,
} from 'antd';
import { LockOutlined, LoadingOutlined } from '@ant-design/icons';
import { useSession } from '../session/SessionContext';
import {
  useAllTeachers, useCreateExport, useExportJobs, useSchools,
} from '../api/queries';
import { exportsApi } from '../api/endpoints';
import { download } from '../api/download';
import { PageHead } from '../components/common';
import ServerTable from '../components/ServerTable';

const fmt = (d) => d.format('YYYY-MM-DD');
const HEADS = ['head', 'group_head'];

const REPORTS = [
  {
    key: 'plan', title: 'План и нормы', desc: 'Ежедневный план, договорная нагрузка и нормы за период',
    roles: ['teacher', 'director', ...HEADS], teacher: true, badge: 'plan',
    includes: ['по дням: плановые часы по видам работ', 'договорная нагрузка и норма за ставку', 'доля ставки и периоды действия норм'],
  },
  {
    key: 'plan_vs_fact', title: 'План против факта', desc: 'По дням и видам работ, с отклонениями',
    roles: ['teacher', ...HEADS], teacher: true, badge: 'heads',
    includes: ['по дням: план и факт, ч, по видам работ', 'отклонение, факт дома и в школе', 'статус дня; пропуски — «нет данных», не 0'],
  },
  {
    key: 'summary', title: 'Недельная и месячная сводка', desc: 'Агрегаты план/факт, выходные часы, полнота данных',
    roles: HEADS, teacher: true, badge: 'heads',
    includes: ['по неделям и месяцам: план, факт, отклонение', 'часы в выходные', 'полнота заполнения дней'],
  },
  {
    key: 'surveys', title: 'Динамика анкет', desc: 'Оценки по шкалам и охват опросами — без текстов',
    roles: ['teacher', ...HEADS], teacher: true, badge: 'heads',
    includes: ['оценки по шкалам 1–5 по датам', 'охват: заполнено из ожидаемого', 'для руководителя — педагоги под псевдонимами'],
  },
  {
    key: 'imports', title: 'История импортов', desc: 'Кто и когда загружал Excel, итог проверки',
    roles: ['director', ...HEADS], teacher: false, badge: 'plan',
    includes: ['дата, автор и файл', 'число добавленных, обновлённых и пропущенных строк', 'ошибки проверки'],
  },
  {
    key: 'audit', title: 'Журнал аудита', desc: 'Просмотры чувствительных данных и выгрузки',
    roles: HEADS, teacher: false, badge: 'heads',
    includes: ['кто, когда и что открывал или выгружал', 'изменения плана и справочников'],
  },
  {
    key: 'ml_dataset', title: 'ML-датасет', desc: 'Признаки нагрузки и самочувствия, педагоги под псевдонимами',
    roles: HEADS, teacher: false, badge: 'research', csvOnly: true,
    includes: ['псевдоним педагога вместо ФИО', 'скользящие показатели анкет', 'плановые и фактические часы'],
  },
];
const BADGES = {
  plan: { label: 'и директор', cls: 'badge-plan' },
  heads: { label: 'главы', cls: 'badge-heads' },
  research: { label: 'псевдоним.', cls: 'badge-research' },
};
const REPORT_TITLE = Object.fromEntries(REPORTS.map((r) => [r.key, r.title]));
const STATUS = {
  running: { label: 'Формируется', cls: 'tag-partial' },
  ready: { label: 'Готов', cls: 'tag-ok' },
  expired: { label: 'Истёк срок', cls: '' },
  failed: { label: 'Ошибка', cls: 'tag-err' },
};

export default function Reports() {
  const { role, school, schools: sessionSchools, teacherId: ownTeacherId } = useSession();
  const { message } = App.useApp();
  const isTeacher = role === 'teacher';
  const multiSchool = HEADS.includes(role);
  const available = REPORTS.filter((r) => r.roles.includes(role));

  const [reportKey, setReportKey] = useState(available[0]?.key);
  const [range, setRange] = useState(() => [dayjs().startOf('isoWeek').subtract(3, 'week'), dayjs()]);
  const [schoolIds, setSchoolIds] = useState(() => (school ? [school.id] : []));
  const [teacherId, setTeacherId] = useState();
  const [format, setFormat] = useState('xlsx');
  const [pg, setPg] = useState({ page: 1, pageSize: 10 });

  const report = available.find((r) => r.key === reportKey) ?? available[0];
  const schoolsQ = useSchools();
  const teachersQ = useAllTeachers(!isTeacher && schoolIds.length === 1 ? schoolIds[0] : null);
  const jobs = useExportJobs(pg);
  const create = useCreateExport();

  useEffect(() => { if (report?.csvOnly) setFormat('csv'); }, [report?.csvOnly]);
  useEffect(() => { setTeacherId(undefined); }, [schoolIds]);

  const schoolName = useMemo(() => Object.fromEntries((schoolsQ.data ?? sessionSchools ?? []).map((s) => [s.id, s.name.replace(/^МБОУ «|»$/g, '').replace(/ — .*/, '')])), [schoolsQ.data, sessionSchools]);

  const submit = async (body) => {
    try {
      await create.mutateAsync(body);
      setPg((p) => ({ ...p, page: 1 }));
      message.success('Отчёт поставлен в очередь — он появится в списке ниже');
    } catch (e) {
      message.error(e.message);
    }
  };

  const onCreate = () => {
    if (!schoolIds.length) { message.warning('Выберите школу'); return; }
    submit({
      report: report.key,
      school_ids: schoolIds,
      teacher_id: isTeacher ? ownTeacherId : (report.teacher ? teacherId ?? null : null),
      date_from: fmt(range[0]),
      date_to: fmt(range[1]),
      format: report.csvOnly ? 'csv' : format,
    });
  };

  const columns = [
    { title: 'Когда', dataIndex: 'created_at', render: (v) => <span className="muted" style={{ whiteSpace: 'nowrap' }}>{dayjs(v).format('D MMM, HH:mm')}</span> },
    { title: 'Отчёт', dataIndex: 'report', render: (v) => <span style={{ fontWeight: 500 }}>{REPORT_TITLE[v] ?? v}</span> },
    {
      title: 'Параметры', key: 'params',
      render: (_, j) => (
        <span className="muted">
          {(j.params.school_ids ?? []).map((id) => schoolName[id] ?? id).join(', ')}
          {' · '}{dayjs(j.params.date_from).format('D.MM')}–{dayjs(j.params.date_to).format('D.MM.YY')}
          {' · '}{j.params.format?.toUpperCase()}
        </span>
      ),
    },
    {
      title: 'Статус', dataIndex: 'status',
      render: (v) => <Tag bordered={false} className={STATUS[v]?.cls} icon={v === 'running' ? <LoadingOutlined /> : null}>{STATUS[v]?.label ?? v}</Tag>,
    },
    {
      title: 'Файл', key: 'file', align: 'right',
      render: (_, j) => {
        if (j.status === 'ready') {
          return (
            <span style={{ whiteSpace: 'nowrap' }}>
              <Button type="link" style={{ padding: 0 }} onClick={() => download(() => exportsApi.file(j.id), `${j.report}_${j.params.date_from}.${j.params.format}`, message)}>Скачать</Button>
              {j.expires_at && <span className="muted" style={{ fontSize: 12, marginLeft: 8 }}>до {dayjs(j.expires_at).format('D MMM')}</span>}
            </span>
          );
        }
        if (j.status === 'expired' || j.status === 'failed') {
          return <Button type="link" style={{ padding: 0 }} onClick={() => submit({ report: j.report, ...j.params })}>Сформировать снова</Button>;
        }
        return <span className="muted">—</span>;
      },
    },
  ];

  if (!report) return <div className="page"><PageHead title="Отчёты и экспорт" sub="Для вашей роли отчётов нет" /></div>;

  return (
    <div className="page">
      <PageHead title="Отчёты и экспорт" sub="Выгрузка применяет те же права, что и экраны: в файл попадает только то, что вам разрешено видеть." />

      <div className="reports-layout">
        <Card className="report-list" styles={{ body: { padding: 8 } }}>
          <div role="radiogroup" aria-label="Тип отчёта">
            {available.map((r) => (
              <button
                key={r.key}
                type="button"
                role="radio"
                aria-checked={r.key === report.key}
                className={`report-item${r.key === report.key ? ' report-item--on' : ''}`}
                onClick={() => setReportKey(r.key)}
              >
                <span className="report-item-head">
                  <span>{r.title}</span>
                  {!isTeacher && <span className={`report-badge ${BADGES[r.badge].cls}`}>{BADGES[r.badge].label}</span>}
                </span>
                <span className="report-item-desc">{r.desc}</span>
              </button>
            ))}
          </div>
        </Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
          <Card title={report.title}>
            <div className="report-params">
              <label className="field">
                <span>Период</span>
                <DatePicker.RangePicker
                  value={range}
                  format="D MMM YYYY"
                  allowClear={false}
                  className="range-compact"
                  disabledDate={(d) => d.isAfter(dayjs().add(1, 'month'), 'day')}
                  onChange={(r) => r && setRange(r)}
                />
              </label>
              <label className="field">
                <span>{multiSchool ? 'Школы' : 'Школа'}</span>
                {multiSchool ? (
                  <Select
                    mode="multiple"
                    value={schoolIds}
                    onChange={setSchoolIds}
                    loading={schoolsQ.isPending}
                    style={{ minWidth: 260, maxWidth: 420 }}
                    options={(schoolsQ.data ?? []).map((s) => ({ value: s.id, label: schoolName[s.id] }))}
                    placeholder="Выберите школы"
                  />
                ) : <span className="school-chip"><LockOutlined aria-hidden /> {school ? schoolName[school.id] ?? school.name : '—'}</span>}
              </label>
              {report.teacher && !isTeacher && (
                <label className="field">
                  <span>Преподаватель</span>
                  <Select
                    allowClear
                    showSearch
                    optionFilterProp="label"
                    placeholder={schoolIds.length === 1 ? 'Все преподаватели' : 'Все (выберите одну школу для фильтра)'}
                    disabled={schoolIds.length !== 1}
                    value={teacherId}
                    onChange={setTeacherId}
                    style={{ minWidth: 240 }}
                    options={(teachersQ.data?.items ?? []).map((t) => ({ value: t.id, label: t.full_name ?? t.external_id }))}
                  />
                </label>
              )}
              <div className="field">
                <span>Формат</span>
                <Segmented
                  value={report.csvOnly ? 'csv' : format}
                  onChange={setFormat}
                  disabled={report.csvOnly}
                  options={[{ value: 'xlsx', label: 'XLSX' }, { value: 'csv', label: 'CSV' }]}
                />
              </div>
            </div>

            <div className="report-info">
              <div className="report-info-box">
                <div className="report-info-title">В файл попадёт</div>
                <ul>{report.includes.map((x) => <li key={x}>{x}</li>)}</ul>
                {isTeacher && <div className="muted" style={{ fontSize: 13, marginTop: 6 }}>Только ваши данные.</div>}
              </div>
              <div className="report-info-box">
                <div className="report-info-title"><LockOutlined aria-hidden /> Не включается никогда</div>
                <ul className="muted">
                  <li>тексты комментариев к анкетам</li>
                  <li>контакты и логины</li>
                  {role === 'director' && <li>фактические часы и самочувствие</li>}
                </ul>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Button type="primary" size="large" loading={create.isPending} onClick={onCreate}>Сформировать</Button>
              <span className="muted" style={{ fontSize: 13 }}>Отчёт готовится в фоне и появится в списке ниже</span>
            </div>
          </Card>

          <Card title="Мои выгрузки">
            <ServerTable
              query={jobs}
              columns={columns}
              page={pg.page}
              pageSize={pg.pageSize}
              onPageChange={(page, pageSize) => setPg({ page, pageSize })}
              size="middle"
              locale={{ emptyText: 'Выгрузок пока нет' }}
            />
            <div className="muted" style={{ fontSize: 13, marginTop: 10 }}>Готовые файлы хранятся 7 дней, затем их нужно сформировать заново.</div>
          </Card>
        </div>
      </div>
    </div>
  );
}
