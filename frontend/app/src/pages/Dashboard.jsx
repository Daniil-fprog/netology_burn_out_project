import { useMemo, useState } from 'react';
import dayjs from 'dayjs';
import { App, Button, Card, Col, Row, Table, Tooltip } from 'antd';
import { DownloadOutlined, LockOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { useSession } from '../session/SessionContext';
import { useAllTeachers, usePlannedDashboard } from '../api/queries';
import { filesApi } from '../api/endpoints';
import { download } from '../api/download';
import { PageHead, Kpi, fmtN } from '../components/common';
import PeriodFilter, { presetRange } from '../components/PeriodFilter';
import { KpiSkeleton, TableSkeleton } from '../components/Skeletons';
import { colors } from '../theme';

const ACADEMIC_HOUR = 0.75;
const toAcademic = (h) => (h == null ? null : h / ACADEMIC_HOUR);
const fmt1 = (v) => (v == null ? '—' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(v));

function BarsByWeek({ weekly }) {
  const max = Math.max(1, ...weekly.map((w) => w.value));
  return (
    <div className="vbars" role="img" aria-label="Плановые часы по неделям">
      {weekly.map((w) => (
        <div key={w.week_start} className="vbar">
          <span className="vbar-value">{fmt1(w.value)}</span>
          <div className="vbar-fill" style={{ height: `${(w.value / max) * 100}%`, background: colors.plan }} />
          <span className="vbar-label">{w.label}</span>
        </div>
      ))}
    </div>
  );
}

function BarsBySubject({ rows }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="hbars">
      {rows.map((r) => (
        <div key={r.subject} className="hbar">
          <span className="hbar-name" title={r.subject}>{r.subject}</span>
          <div className="hbar-track"><div className="hbar-fill" style={{ width: `${(r.value / max) * 100}%`, background: colors.plan }} /></div>
          <span className="hbar-value">{fmt1(r.value)}</span>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const { school, role } = useSession();
  const { message } = App.useApp();
  const [period, setPeriod] = useState({ kind: 'month', ...presetRange('month') });
  const params = { dateFrom: period.dateFrom, dateTo: period.dateTo };
  const dash = usePlannedDashboard(school?.id, params);
  const teachersQ = useAllTeachers(school?.id);

  const view = useMemo(() => {
    const d = dash.data;
    if (!d) return null;
    const weeks = Math.max(1, d.weekly.length);
    const norms = Object.fromEntries((teachersQ.data?.items ?? []).map((t) => [t.id, t.current_norm]));
    const rows = d.teachers.map((t) => {
      const norm = norms[t.teacher_id];
      const planPerWeek = toAcademic(t.planned_teaching_hours) / weeks;
      const contract = norm?.contract_teaching_hours_per_week ?? null;
      return {
        ...t,
        contract,
        rate: norm?.rate_fraction ?? null,
        planPerWeek,
        deviation: contract == null ? null : planPerWeek - contract,
      };
    });
    const perWeek = rows.map((r) => r.planPerWeek);
    const matches = rows.filter((r) => r.deviation != null && Math.abs(r.deviation) < 0.5).length;
    return {
      weeks,
      rows,
      teachingAcademic: toAcademic(d.kpi.planned_teaching_hours),
      avgPerWeek: perWeek.length ? perWeek.reduce((s, x) => s + x, 0) / perWeek.length : null,
      medianPerWeek: d.kpi.median_teaching_hours == null ? null : toAcademic(d.kpi.median_teaching_hours) / weeks,
      matches,
      totalAstro: d.teachers.reduce((s, t) => s + t.planned_hours, 0),
      weekly: d.weekly.map((w) => {
        const s = dayjs(w.week_start);
        const e = s.add(6, 'day');
        return { ...w, value: w.hours, label: s.month() === e.month() ? `${s.format('D')}–${e.format('D MMM')}` : `${s.format('D MMM')}–${e.format('D MMM')}` };
      }),
      subjects: d.by_subject.map((x) => ({ ...x, value: x.hours })).sort((a, b) => b.value - a.value),
    };
  }, [dash.data, teachersQ.data]);

  const columns = [
    {
      title: 'Преподаватель', dataIndex: 'full_name',
      render: (v, r) => <Link to={`/workload/plans?teacher=${r.teacher_id}`}>{v ?? r.teacher_id}</Link>,
      sorter: (a, b) => (a.full_name ?? '').localeCompare(b.full_name ?? ''),
    },
    { title: 'Предмет', dataIndex: 'subject', render: (v) => <span className="muted">{v}</span> },
    { title: 'Договор, уч.ч/нед', dataIndex: 'contract', align: 'right', render: fmtN },
    { title: 'Доля ставки', dataIndex: 'rate', align: 'right', render: (v) => (v == null ? '—' : v.toFixed(2).replace('.', ',')) },
    {
      title: 'План, уч.ч/нед', dataIndex: 'planPerWeek', align: 'right',
      render: (v) => <span className="num" style={{ color: colors.planText, fontWeight: 600 }}>{fmt1(v)}</span>,
      sorter: (a, b) => a.planPerWeek - b.planPerWeek,
    },
    {
      title: 'Откл. от договора, уч.ч', dataIndex: 'deviation', align: 'right',
      render: (v) => {
        if (v == null) return '—';
        if (Math.abs(v) < 0.05) return <span className="muted">0</span>;
        return <span className="num" style={{ color: colors.planText, fontWeight: 600 }}>{v > 0 ? '+' : '−'}{fmt1(Math.abs(v))}</span>;
      },
      sorter: (a, b) => (a.deviation ?? 0) - (b.deviation ?? 0),
    },
    { title: 'Всего план, астр.ч', dataIndex: 'planned_hours', align: 'right', render: (v) => <span className="num">{fmt1(v)}</span> },
  ];

  return (
    <div className="page">
      <PageHead
        title="Плановая нагрузка"
        sub="Только план и установленные нормы. Факт и опросы здесь не показываются."
        extra={(
          <Button
            icon={<DownloadOutlined />}
            onClick={() => download(() => filesApi.export(school.id, { ...params, report: 'planned' }), `plan_${params.dateFrom}_${params.dateTo}.xlsx`, message)}
          >
            Скачать сводку XLSX
          </Button>
        )}
      />

      <Card size="small" style={{ marginBottom: 16 }}>
        <div className="filter-bar">
          <PeriodFilter value={period} onChange={setPeriod} />
          <Tooltip title={role === 'director' ? 'Директору школа задана фиксированно' : 'Школа выбирается в шапке'}>
            <span className="school-chip"><LockOutlined aria-hidden /> {school?.name}</span>
          </Tooltip>
        </div>
      </Card>

      {!view ? (
        <>
          <KpiSkeleton count={5} />
          <Card><TableSkeleton rows={6} /></Card>
        </>
      ) : (
        <div style={{ opacity: dash.isPlaceholderData ? 0.6 : 1, transition: 'opacity .2s' }}>
          <div className="kpi-grid">
            <Kpi label="Учебных часов в плане" value={fmt1(view.teachingAcademic)} unit="уч.ч" tone="plan" hint={`за ${view.weeks} нед.`} />
            <Kpi label="Преподавателей" value={dash.data.kpi.teacher_count} hint="с планом за период" tone="plan" />
            <Kpi label="Среднее на преподавателя" value={fmt1(view.avgPerWeek)} unit="уч.ч/нед" tone="plan" hint={`медиана ${fmt1(view.medianPerWeek)}`} />
            <Kpi label="Совпадает с договором" value={`${view.matches} из ${view.rows.length}`} tone="plan" hint="отклонение меньше 0,5 уч.ч/нед" />
            <Kpi label="Всего план" value={fmt1(view.totalAstro)} unit="астр.ч" tone="plan" hint="все виды работ" />
          </div>

          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            <Col xs={24} lg={12}>
              <Card title="Динамика по неделям" extra={<span className="muted" style={{ fontSize: 13 }}>астр.ч, все виды работ</span>} style={{ height: '100%' }}>
                {view.weekly.length ? <BarsByWeek weekly={view.weekly} /> : <div className="muted">Нет плана за период</div>}
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="Нагрузка по предметам" extra={<span className="muted" style={{ fontSize: 13 }}>астр.ч за период, все виды работ</span>} style={{ height: '100%' }}>
                {view.subjects.length ? <BarsBySubject rows={view.subjects} /> : <div className="muted">Нет плана за период</div>}
              </Card>
            </Col>
          </Row>

          <Card
            title="Преподаватели"
            extra={<span className="muted" style={{ fontSize: 13 }}>Нагрузка выше нормы за ставку не считается нарушением</span>}
          >
            <Table
              rowKey="teacher_id"
              dataSource={view.rows}
              columns={columns}
              pagination={view.rows.length > 20 ? { pageSize: 20, showSizeChanger: false } : false}
              scroll={{ x: 720 }}
              size="middle"
            />
          </Card>
        </div>
      )}
    </div>
  );
}
