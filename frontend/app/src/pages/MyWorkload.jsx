import { useEffect, useMemo, useState } from 'react';
import dayjs from 'dayjs';
import {
  Alert, App, Button, Card, Col, DatePicker, Form, Input, InputNumber, Modal, Row, Segmented, Select, Skeleton, Space, Tag, Tooltip,
} from 'antd';
import {
  LeftOutlined, RightOutlined, PlusOutlined, DeleteOutlined, EditOutlined, CopyOutlined,
} from '@ant-design/icons';
import { useSession } from '../session/SessionContext';
import { useDailyRange, useSaveDay, useWorkTypes } from '../api/queries';
import { PageHead, StatusTag, Kpi, Deviation, fmtH } from '../components/common';
import { KpiSkeleton, TableSkeleton } from '../components/Skeletons';
import { colors } from '../theme';

const ACADEMIC_HOUR = 0.75;
const PLACES = [
  { value: 'school', label: 'В школе' },
  { value: 'home', label: 'Дома' },
  { value: 'other', label: 'Другое' },
];
const fmtDate = (d) => d.format('YYYY-MM-DD');
const sum = (arr, f) => arr.reduce((s, x) => s + (f(x) ?? 0), 0);

function lessonsWord(n) {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return 'урок';
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return 'урока';
  return 'уроков';
}

// backend не хранит 0 ч: в завершённом дне пустая строка = 0, в черновике — нет данных
function buildRows(day) {
  if (!day) return [];
  const planItems = day.plan?.items ?? [];
  const entries = day.actual?.entries ?? [];
  const completed = day.actual?.status === 'completed';
  const planned = planItems.map((p) => {
    const e = entries.find((x) => x.planned_work_item_id === p.id);
    return {
      key: p.id,
      planId: p.id,
      workTypeId: p.work_type_id,
      planHours: p.duration_hours,
      hours: e ? e.duration_hours : (completed ? 0 : null),
      place: e?.location ?? 'school',
      comment: e?.comment ?? '',
      unplanned: false,
    };
  });
  const extra = entries.filter((e) => !e.planned_work_item_id).map((e) => ({
    key: e.id, planId: null, workTypeId: e.work_type_id, planHours: null,
    hours: e.duration_hours, place: e.location, comment: e.comment ?? '', unplanned: true,
  }));
  return [...planned, ...extra];
}

function WeekStrip({ days, selected, today, onPick }) {
  return (
    <>
      <div className="week-strip" role="group" aria-label="Дни недели">
        {days.map(({ date, status, hasData }) => {
          const d = dayjs(date);
          const future = date > today;
          const active = date === selected;
          const st = colors.status[status];
          return (
            <button
              key={date}
              type="button"
              aria-pressed={active}
              className={`week-day${active ? ' week-day--active' : ''}${!hasData ? ' week-day--off' : ''}`}
              onClick={() => onPick(date)}
              title={`${d.format('D MMMM')} — ${future ? 'будущая дата' : st.label.toLowerCase()}`}
            >
              <span className="dow">{d.format('dd')}</span>
              <span className="dnum" style={{ color: date === today ? colors.primary : undefined }}>{d.date()}</span>
              <span className="dot" style={{ background: future || !hasData ? 'transparent' : (status === 'not_started' ? '#B9C4C1' : st.fg) }} />
            </button>
          );
        })}
      </div>
      <div className="week-legend">
        <span><span className="dot" style={{ background: colors.status.completed.fg }} />завершён</span>
        <span><span className="dot" style={{ background: colors.status.draft.fg }} />черновик</span>
        <span><span className="dot" style={{ background: '#B9C4C1' }} />не начат</span>
      </div>
    </>
  );
}

function UnplannedModal({ open, workTypes, onCancel, onAdd }) {
  const [form] = Form.useForm();
  const wt = Form.useWatch('workTypeId', form);
  const needComment = workTypes.find((w) => w.id === wt)?.requires_comment;
  return (
    <Modal
      open={open}
      title="Внеплановая работа"
      okText="Добавить"
      cancelText="Отмена"
      onCancel={onCancel}
      destroyOnHidden
      onOk={async () => {
        const v = await form.validateFields();
        onAdd(v);
        form.resetFields();
      }}
    >
      <Form form={form} layout="vertical" initialValues={{ place: 'school' }} preserve={false} requiredMark={false}>
        <Form.Item name="workTypeId" label="Вид работы" rules={[{ required: true, message: 'Выберите вид работы' }]}>
          <Select
            showSearch
            optionFilterProp="label"
            placeholder="Например, замена"
            options={workTypes.map((w) => ({ value: w.id, label: w.name }))}
          />
        </Form.Item>
        <Form.Item name="hours" label="Длительность, ч" rules={[{ required: true, message: 'Укажите время' }]}>
          <InputNumber min={0.25} max={24} step={0.25} decimalSeparator="," inputMode="decimal" style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="place" label="Где выполнялась">
          <Segmented block options={PLACES} />
        </Form.Item>
        <Form.Item
          name="comment"
          label={needComment ? 'Что делали (обязательно)' : 'Что делали'}
          rules={needComment ? [{ required: true, whitespace: true, message: 'Для этого вида работы нужен комментарий' }] : []}
        >
          <Input.TextArea rows={2} maxLength={500} placeholder="Например, репетиция концерта" />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default function MyWorkload() {
  const { school, user } = useSession();
  const { message, modal } = App.useApp();
  const today = fmtDate(dayjs());
  const [date, setDate] = useState(today);
  const [rows, setRows] = useState([]);
  const [dirty, setDirty] = useState(false);
  const [editing, setEditing] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  const weekStart = dayjs(date).startOf('isoWeek');
  const range = { dateFrom: fmtDate(weekStart), dateTo: fmtDate(weekStart.add(6, 'day')) };
  const week = useDailyRange(school?.id, range);
  const workTypesQ = useWorkTypes();
  const save = useSaveDay(school?.id);

  const workTypes = workTypesQ.data ?? [];
  const wtById = useMemo(() => Object.fromEntries(workTypes.map((w) => [w.id, w])), [workTypes]);
  const lessonsTypeId = workTypes.find((w) => w.code === 'lessons')?.id;

  const weekReady = week.data && !week.isPlaceholderData;
  const day = weekReady ? week.data.items.find((r) => r.work_date === date) ?? null : undefined;
  const status = day?.actual?.status ?? 'not_started';
  const isFuture = date > today;
  const readOnly = isFuture || !editing;

  useEffect(() => {
    if (day === undefined) return;
    setRows(buildRows(day));
    setDirty(false);
    setEditing(day?.actual?.status !== 'completed');
  }, [date, weekReady, day?.actual?.updated_at]);

  const strip = Array.from({ length: 7 }, (_, i) => {
    const d = fmtDate(weekStart.add(i, 'day'));
    const r = week.data?.items.find((x) => x.work_date === d);
    return { date: d, status: r?.actual?.status ?? 'not_started', hasData: Boolean(r) || d <= today };
  });

  const totals = useMemo(() => {
    const filled = rows.filter((r) => r.hours != null);
    const plan = sum(rows, (r) => r.planHours);
    const fact = filled.length ? sum(filled, (r) => r.hours) : null;
    return {
      plan: rows.some((r) => r.planHours != null) ? plan : null,
      fact,
      deviation: fact != null && rows.some((r) => r.planHours != null) ? fact - plan : null,
      home: sum(filled.filter((r) => r.place === 'home'), (r) => r.hours),
      unplanned: sum(filled.filter((r) => r.unplanned), (r) => r.hours),
      missing: rows.filter((r) => r.hours == null).length,
    };
  }, [rows]);

  const update = (key, patch) => {
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
    setDirty(true);
  };

  const pickDate = (d) => {
    if (d === date) return;
    if (!dirty) { setDate(d); return; }
    modal.confirm({
      title: 'Есть несохранённые изменения',
      content: 'Перейти к другому дню без сохранения?',
      okText: 'Перейти',
      cancelText: 'Остаться',
      onOk: () => setDate(d),
    });
  };

  const submit = async (complete) => {
    if (complete && totals.missing > 0) {
      message.warning(`Не заполнено строк: ${totals.missing}. Укажите время или 0, если работа не выполнялась.`);
      return;
    }
    const entries = rows
      .filter((r) => r.hours != null && r.hours > 0)
      .map((r) => ({
        planned_work_item_id: r.planId,
        work_type_id: r.workTypeId,
        duration_hours: r.hours,
        location: r.place,
        comment: r.comment?.trim() || null,
      }));
    const body = { status: complete ? 'completed' : 'draft', entries };
    try {
      await save.mutateAsync({
        recordId: day?.actual?.id,
        body: day?.actual ? body : { ...body, work_date: date, day_type: day?.day_type ?? (dayjs(date).isoWeekday() > 5 ? 'Выходной' : 'Учебный день') },
      });
      setDirty(false);
      message.success(complete ? 'День завершён' : 'Черновик сохранён');
    } catch (e) {
      message.error(e.message);
    }
  };

  const fillFromPlan = () => {
    setRows((rs) => rs.map((r) => (r.hours == null && r.planHours != null ? { ...r, hours: r.planHours } : r)));
    setDirty(true);
  };

  const sub = (r) => {
    const parts = [];
    if (r.workTypeId === lessonsTypeId && r.planHours) {
      const n = Math.round(r.planHours / ACADEMIC_HOUR);
      parts.push(`${n} ${lessonsWord(n)}`);
    }
    if (r.planHours != null) parts.push(`план ${fmtH(r.planHours)} ч`);
    if (r.unplanned && r.comment) parts.push(r.comment);
    return parts.join(' · ');
  };

  const loading = day === undefined || workTypesQ.isPending;
  const over = totals.deviation != null && totals.deviation > 0.05;

  return (
    <div className="page page--narrow page--with-footer">
      <PageHead title="Моя нагрузка" sub="Сколько времени фактически заняла каждая работа" />

      <Card size="small" style={{ marginBottom: 12 }}>
        <div className="date-nav">
          <Button type="text" icon={<LeftOutlined />} aria-label="Предыдущая неделя" onClick={() => pickDate(fmtDate(dayjs(date).subtract(1, 'week')))} />
          <DatePicker
            value={dayjs(date)}
            onChange={(d) => d && pickDate(fmtDate(d))}
            format={(v) => v.format('dd, D MMMM YYYY')}
            allowClear={false}
            variant="borderless"
            inputReadOnly
            suffixIcon={null}
            className="date-nav-picker"
            aria-label="Выбрать дату"
          />
          <Button type="text" icon={<RightOutlined />} aria-label="Следующая неделя" onClick={() => pickDate(fmtDate(dayjs(date).add(1, 'week')))} />
        </div>
        {week.isPending ? <Skeleton.Input active block style={{ height: 64 }} /> : <WeekStrip days={strip} selected={date} today={today} onPick={pickDate} />}
      </Card>

      {loading ? (
        <>
          <KpiSkeleton count={4} />
          <Card><TableSkeleton rows={6} /></Card>
        </>
      ) : (
        <>
          <Row gutter={[10, 10]} style={{ marginBottom: 12 }}>
            <Col xs={12} sm={6}><Kpi label="План" value={fmtH(totals.plan)} unit="ч" tone="plan" /></Col>
            <Col xs={12} sm={6}><Kpi label="Факт" value={fmtH(totals.fact)} unit="ч" tone="fact" /></Col>
            <Col xs={12} sm={6}>
              <Kpi label="Разница" value={<Deviation value={totals.deviation} unit="" />} unit="ч" highlight={over} />
            </Col>
            <Col xs={12} sm={6}><Kpi label="Дома / внеплан" value={`${fmtH(totals.home)} / ${fmtH(totals.unplanned)}`} unit="ч" /></Col>
          </Row>

          <Card
            title={<Space>Работы за день <StatusTag status={status} /></Space>}
            extra={!isFuture && readOnly && <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>Изменить</Button>}
            styles={{ body: { paddingTop: 0 } }}
          >
            {isFuture && <Alert type="info" showIcon message="Будущая дата: можно посмотреть план, факт вносится после." style={{ margin: '12px 0' }} />}
            {!isFuture && !readOnly && totals.missing > 0 && (
              <div className="missing-hint">
                Пустое поле — «нет данных», а не 0. Если работу не делали, поставьте 0.
              </div>
            )}
            {!rows.length && (
              <div className="muted" style={{ padding: '16px 0' }}>
                На этот день плановых работ нет.{!isFuture && ' Если вы работали — добавьте внеплановую работу.'}
              </div>
            )}

            {rows.map((r) => {
              const wt = wtById[r.workTypeId];
              return (
                <div className="work-row" key={r.key}>
                  <div className="wr-main">
                    <div className="wr-title">
                      <div style={{ fontWeight: 500, lineHeight: 1.3 }}>
                        {wt?.name ?? 'Вид работы'}
                        {r.unplanned && <Tag bordered={false} className="tag-unplanned">внеплан</Tag>}
                      </div>
                      <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>{sub(r)}</div>
                    </div>
                    <label className="wr-fact">
                      <span>Факт, ч</span>
                      <InputNumber
                        aria-label={`Факт: ${wt?.name ?? ''}`}
                        value={r.hours}
                        min={0}
                        max={24}
                        step={0.25}
                        decimalSeparator=","
                        inputMode="decimal"
                        placeholder="—"
                        disabled={readOnly}
                        className={r.hours == null ? 'input-missing' : undefined}
                        onChange={(v) => update(r.key, { hours: v })}
                        style={{ width: '100%' }}
                      />
                    </label>
                    {r.unplanned && !readOnly && (
                      <Tooltip title="Удалить">
                        <Button
                          type="text"
                          icon={<DeleteOutlined />}
                          aria-label="Удалить запись"
                          onClick={() => { setRows((rs) => rs.filter((x) => x.key !== r.key)); setDirty(true); }}
                        />
                      </Tooltip>
                    )}
                  </div>
                  <Segmented
                    block
                    size="middle"
                    aria-label="Где выполнялась работа"
                    options={PLACES}
                    value={r.place}
                    disabled={readOnly}
                    onChange={(v) => update(r.key, { place: v })}
                  />
                </div>
              );
            })}

            {!readOnly && (
              <div className="work-actions">
                <Button icon={<PlusOutlined />} className="btn-dashed-primary" onClick={() => setModalOpen(true)}>Внеплановая работа</Button>
                {rows.some((r) => r.hours == null && r.planHours != null) && (
                  <Button icon={<CopyOutlined />} onClick={fillFromPlan}>Заполнить пустые по плану</Button>
                )}
              </div>
            )}
          </Card>

          {day?.actual?.updated_at && (
            <div className="muted" style={{ fontSize: 13, marginTop: 8 }}>
              Изменено {dayjs(day.actual.updated_at).format('D MMMM, HH:mm')} · {user.name}
            </div>
          )}

          {!readOnly && (
            <div className="sticky-footer">
              <div className="sticky-footer-inner">
                <span style={{ fontSize: 14, color: totals.missing ? colors.status.draft.fg : colors.muted }}>
                  {totals.missing ? `Не заполнено: ${totals.missing}` : 'Все строки заполнены'}
                </span>
                <div className="sticky-footer-btns">
                  <Button size="large" loading={save.isPending && save.variables?.body?.status === 'draft'} disabled={save.isPending} onClick={() => submit(false)}>
                    Сохранить черновик
                  </Button>
                  <Button size="large" type="primary" loading={save.isPending && save.variables?.body?.status === 'completed'} disabled={save.isPending} onClick={() => submit(true)}>
                    Завершить день
                  </Button>
                </div>
              </div>
            </div>
          )}

          <UnplannedModal
            open={modalOpen}
            workTypes={workTypes}
            onCancel={() => setModalOpen(false)}
            onAdd={(v) => {
              setRows((rs) => [...rs, {
                key: `new-${Date.now()}`, planId: null, planHours: null, unplanned: true,
                workTypeId: v.workTypeId, hours: v.hours, place: v.place, comment: v.comment ?? '',
              }]);
              setDirty(true);
              setModalOpen(false);
            }}
          />
        </>
      )}
    </div>
  );
}
