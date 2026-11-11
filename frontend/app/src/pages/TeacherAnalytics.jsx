import { useMemo, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import dayjs from 'dayjs';
import { App, Button, Card, Col, DatePicker, Row, Select } from 'antd';
import { DownloadOutlined, LockOutlined } from '@ant-design/icons';
import { useSession } from '../session/SessionContext';
import {
  useAllTeachers, useDailyRange, useSurveyResponses, useWorkTypes,
} from '../api/queries';
import { filesApi } from '../api/endpoints';
import { download } from '../api/download';
import { Kpi, fmtH } from '../components/common';
import { KpiSkeleton, TableSkeleton } from '../components/Skeletons';
import { colors } from '../theme';

const fmtDate = (d) => d.format('YYYY-MM-DD');
const SCALE_FG = ['#145A50', '#145A50', '#0E3F38', '#FFFFFF', '#FFFFFF'];
const MAX_DAYS = 92;
const sum = (arr, f) => arr.reduce((s, x) => s + (f(x) ?? 0), 0);

function Score({ v, label }) {
  if (v == null) return <span className="day-score day-score--empty" title={`${label}: нет ответа`}>—</span>;
  return <span className="day-score" title={`${label}: ${v}`} style={{ background: colors.scale[v - 1], color: SCALE_FG[v - 1] }}>{v}</span>;
}

function DayChart({ days }) {
  const max = Math.max(10, ...days.map((d) => Math.max(d.plan ?? 0, d.fact ?? 0)));
  const cols = { gridTemplateColumns: `84px repeat(${days.length}, minmax(28px, 1fr))` };
  return (
    <div className="day-chart-scroll">
      <div className="day-chart" style={{ minWidth: 84 + days.length * 32 }}>
        <div className="day-grid day-grid--bars" style={cols}>
          <div className="day-axis"><span>{Math.round(max)} ч</span><span>{Math.round(max / 2)} ч</span><span>0</span></div>
          {days.map((d) => (
            <div key={d.date} className="day-bars" title={`${dayjs(d.date).format('D MMMM')}: план ${fmtH(d.plan)} ч, факт ${d.fact == null ? 'нет данных' : `${fmtH(d.fact)} ч`}`}>
              <div className="day-bar" style={{ height: `${((d.plan ?? 0) / max) * 100}%`, background: colors.plan }} />
              {d.fact == null
                ? <div className="day-bar day-bar--missing" />
                : <div className="day-bar" style={{ height: `${(d.fact / max) * 100}%`, background: colors.fact }} />}
            </div>
          ))}
        </div>
        <div className="day-grid" style={cols}>
          <span />
          {days.map((d) => <span key={d.date} className="day-label">{dayjs(d.date).format(d.date.endsWith('-01') ? 'D.MM' : 'D')}</span>)}
        </div>
        <div className="day-grid day-grid--scores" style={cols}>
          <span className="day-row-label">Усталость</span>
          {days.map((d) => <Score key={d.date} v={d.fatigue} label="Усталость" />)}
        </div>
        <div className="day-grid day-grid--scores" style={cols}>
          <span className="day-row-label">Стресс</span>
          {days.map((d) => <Score key={d.date} v={d.stress} label="Стресс" />)}
        </div>
      </div>
    </div>
  );
}

export default function TeacherAnalytics() {
  const { teacherId: paramId } = useParams();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const { school, role, teacherId: ownId, user } = useSession();
  const isTeacher = role === 'teacher';
  const [range, setRange] = useState(() => {
    const end = dayjs();
    return [end.startOf('isoWeek').subtract(3, 'week'), end];
  });

  const teachersQ = useAllTeachers(isTeacher ? null : school?.id);
  const teacherId = isTeacher ? ownId : paramId;
  const params = { dateFrom: fmtDate(range[0]), dateTo: fmtDate(range[1]), teacherId };
  const daily = useDailyRange(school?.id, { ...params, pageSize: 200 }, { enabled: Boolean(teacherId) });
  const surveys = useSurveyResponses(school?.id, { ...params, surveyCode: 'daily_checkin', status: 'submitted', pageSize: 100 }, { enabled: Boolean(teacherId) });
  const workTypesQ = useWorkTypes({ includeArchived: true });

  const teacher = (teachersQ.data?.items ?? []).find((t) => t.id === teacherId);

  const view = useMemo(() => {
    if (!daily.data || !surveys.data || !workTypesQ.data) return null;
    const today = fmtDate(dayjs());
    const byDate = Object.fromEntries(daily.data.items.map((r) => [r.work_date, r]));
    const scores = Object.fromEntries(surveys.data.items.map((r) => [r.assessment_date, r.answers]));
    const days = [];
    for (let d = range[0]; !d.isAfter(range[1], 'day'); d = d.add(1, 'day')) {
      const date = fmtDate(d);
      const r = byDate[date];
      if (!r && (d.isoWeekday() > 5 || date >= today)) continue; // выходные без данных и будущее не показываем
      days.push({
        date,
        row: r,
        plan: r?.plan?.total_hours ?? null,
        fact: r?.actual?.total_hours ?? null,
        fatigue: scores[date]?.fatigue_score ?? null,
        stress: scores[date]?.stress_score ?? null,
      });
    }
    const withFact = days.filter((d) => d.fact != null);
    const planSum = sum(withFact, (d) => d.plan);
    const factSum = sum(withFact, (d) => d.fact);
    const home = sum(withFact, (d) => d.row.actual.at_home_hours);
    const atSchool = sum(withFact, (d) => d.row.actual.at_school_hours);
    const hasEntries = withFact.some((d) => Array.isArray(d.row.actual.entries));
    const unplanned = hasEntries ? withFact.flatMap((d) => (d.row.actual.entries ?? []).filter((e) => !e.planned_work_item_id)) : null;
    const types = workTypesQ.data.map((w) => ({
      code: w.code,
      name: w.name,
      plan: sum(withFact, (d) => d.row.plan?.[`planned_${w.code}_hours`]),
      fact: sum(withFact, (d) => d.row.actual[`actual_${w.code}_hours`]),
    })).filter((t) => t.plan > 0 || t.fact > 0).sort((a, b) => b.fact - a.fact);
    const top = [...types].sort((a, b) => (b.fact - b.plan) - (a.fact - a.plan))[0];
    const expected = days.filter((d) => d.date < today && (d.plan != null || d.fact != null));
    return {
      days,
      planSum,
      factSum,
      home,
      atSchool,
      other: Math.max(0, factSum - home - atSchool),
      deviation: withFact.length ? factSum - planSum : null,
      deviationPct: planSum ? (factSum - planSum) / planSum : null,
      top: top && top.fact - top.plan > 0.05 ? top.name.toLowerCase() : null,
      unplannedHours: unplanned ? sum(unplanned, (e) => Number(e.duration_hours)) : null,
      unplannedCount: unplanned?.length ?? null,
      factDays: withFact.length,
      surveyDays: expected.filter((d) => d.fatigue != null || d.stress != null).length,
      expectedDays: expected.length,
      types,
      typeMax: Math.max(1, ...types.map((t) => Math.max(t.plan, t.fact))),
    };
  }, [daily.data, surveys.data, workTypesQ.data, range]);

  // руководитель без выбранного педагога — открываем первого из списка
  if (!isTeacher && !paramId) {
    const first = teachersQ.data?.items?.[0];
    if (first) return <Navigate to={`/analytics/teachers/${first.id}`} replace />;
  }

  const name = isTeacher ? user.name : teacher?.full_name ?? teacherId ?? '…';
  const norm = teacher?.current_norm;
  const over = view?.deviation != null && view.deviation > 0.05;
  const placeTotal = view ? view.atSchool + view.home + view.other : 0;
  const pct = (v) => (placeTotal ? `${(v / placeTotal) * 100}%` : '0%');

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="muted" style={{ fontSize: 14, marginBottom: 4 }}>
            {isTeacher ? 'Моя аналитика' : <><Link to="/analytics/teachers">Аналитика</Link> / {school?.name}</>}
          </div>
          <h1>{name}</h1>
          <div className="sub">
            {[teacher?.subject, norm && `${norm.contract_teaching_hours_per_week} уч.ч/нед по договору`].filter(Boolean).join(' · ') || ' '}
          </div>
        </div>
        <div className="filter-bar">
          {!isTeacher && (
            <Select
              showSearch
              optionFilterProp="label"
              aria-label="Педагог"
              value={teacherId}
              loading={teachersQ.isPending}
              style={{ minWidth: 220 }}
              options={(teachersQ.data?.items ?? []).map((t) => ({ value: t.id, label: t.full_name ?? t.external_id }))}
              onChange={(v) => navigate(`/analytics/teachers/${v}`)}
            />
          )}
          <DatePicker.RangePicker
            aria-label="Период"
            value={range}
            format="D MMM YYYY"
            allowClear={false}
            className="range-compact"
            disabledDate={(d) => d.isAfter(dayjs(), 'day')}
            onChange={(r) => {
              if (!r) return;
              if (r[1].diff(r[0], 'day') > MAX_DAYS) { message.warning(`Период не больше ${MAX_DAYS} дней`); return; }
              setRange(r);
            }}
          />
          <Button
            icon={<DownloadOutlined />}
            onClick={() => download(() => filesApi.export(school.id, { dateFrom: params.dateFrom, dateTo: params.dateTo, teacherId, report: 'plan_vs_fact' }), `plan_fact_${teacherId}_${params.dateFrom}.xlsx`, message)}
          >
            Экспорт
          </Button>
        </div>
      </div>

      {!view ? (
        <>
          <KpiSkeleton count={5} />
          <Card><TableSkeleton rows={8} /></Card>
        </>
      ) : (
        <div style={{ opacity: daily.isPlaceholderData || surveys.isPlaceholderData ? 0.6 : 1, transition: 'opacity .2s' }}>
          <div className="kpi-grid">
            <Kpi label="План" value={fmtH(view.planSum)} unit="астр.ч" tone="plan" hint="за дни с фактом" />
            <Kpi label="Факт" value={fmtH(view.factSum)} unit="астр.ч" tone="fact" hint={`из них дома ${fmtH(view.home)} ч`} />
            <Kpi
              label="Отклонение"
              value={view.deviation == null ? '—' : `${view.deviation > 0 ? '+' : ''}${fmtH(view.deviation)}`}
              unit={view.deviationPct == null ? 'ч' : `ч · ${view.deviationPct > 0 ? '+' : ''}${Math.round(view.deviationPct * 100)}%`}
              tone={over ? 'fact' : undefined}
              highlight={over}
              hint={view.top ? `больше всего: ${view.top}` : undefined}
            />
            <Kpi
              label="Внеплановая работа"
              value={view.unplannedHours == null ? '—' : fmtH(view.unplannedHours)}
              unit="ч"
              hint={view.unplannedCount == null ? 'нет данных в API' : `${view.unplannedCount} записей`}
            />
            <Kpi label="Полнота данных" value={`${view.factDays} / ${view.expectedDays}`} unit="дней" hint={`анкеты: ${view.surveyDays} из ${view.expectedDays}`} />
          </div>

          <Card
            title="Нагрузка и самочувствие по дням"
            extra={(
              <div className="legend">
                <span><span className="legend-dot" style={{ background: colors.plan }} />план, ч</span>
                <span><span className="legend-dot" style={{ background: colors.fact }} />факт, ч</span>
                <span><span className="legend-dot legend-dot--missing" />нет данных</span>
              </div>
            )}
            style={{ marginBottom: 16 }}
          >
            {view.days.length ? <DayChart days={view.days} /> : <div className="muted">За период нет данных</div>}
            <div className="muted" style={{ fontSize: 13, marginTop: 12 }}>
              Оценки 1–5 из ежедневной анкеты. Это самооценка, а не диагноз; пропуски не заполняются нулями.
            </div>
          </Card>

          <Row gutter={[12, 12]}>
            <Col xs={24} lg={12}>
              <Card title="Структура фактического времени" extra={<span className="muted" style={{ fontSize: 13 }}>план → факт, астр.ч</span>} style={{ height: '100%' }}>
                <div className="type-bars">
                  {view.types.map((t) => (
                    <div key={t.code}>
                      <div className="type-bar-head">
                        <span>{t.name}</span>
                        <span className="num">
                          <span style={{ color: colors.planText }}>{fmtH(t.plan)}</span> → <span style={{ color: colors.factText, fontWeight: 600 }}>{fmtH(t.fact)}</span>
                          {t.fact - t.plan > 0.05 && <span style={{ color: colors.factText, fontSize: 13 }}> (+{fmtH(t.fact - t.plan)})</span>}
                        </span>
                      </div>
                      <div className="type-bar-track">
                        <div className="type-bar-fact" style={{ width: `${(t.fact / view.typeMax) * 100}%` }} />
                        {t.plan > 0 && <div className="type-bar-plan" style={{ left: `calc(${(t.plan / view.typeMax) * 100}% - 1px)` }} />}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="muted" style={{ fontSize: 13, marginTop: 12 }}>Полоса — факт, вертикальная метка — план.</div>
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="Где выполнялась работа" style={{ height: '100%' }}>
                <div className="place-bar" role="img" aria-label={`В школе ${fmtH(view.atSchool)} ч, дома ${fmtH(view.home)} ч, другое ${fmtH(view.other)} ч`}>
                  <div style={{ width: pct(view.atSchool), background: '#2B8272' }} />
                  <div style={{ width: pct(view.home), background: colors.fact }} />
                  <div style={{ width: pct(view.other), background: '#A6D3CB' }} />
                </div>
                <div className="legend" style={{ marginTop: 10 }}>
                  <span><span className="legend-dot" style={{ background: '#2B8272' }} />В школе {fmtH(view.atSchool)} ч</span>
                  <span><span className="legend-dot" style={{ background: colors.fact }} />Дома {fmtH(view.home)} ч</span>
                  <span><span className="legend-dot" style={{ background: '#A6D3CB' }} />Другое {fmtH(view.other)} ч</span>
                </div>
                <div className="comments-note">
                  <LockOutlined aria-hidden />
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: 4 }}>Текстовые комментарии</div>
                    {isTeacher
                      ? <>Ваши тексты видите только вы — они в разделе <Link to="/my/surveys/daily">«Самочувствие»</Link>.</>
                      : 'Тексты видит только сам преподаватель. Руководителю доступны оценки по шкалам и обобщённые результаты.'}
                  </div>
                </div>
              </Card>
            </Col>
          </Row>
        </div>
      )}
    </div>
  );
}
