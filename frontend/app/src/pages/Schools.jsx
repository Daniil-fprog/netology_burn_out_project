import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import {
  App, AutoComplete, Button, Card, Drawer, Empty, Grid, Form, Input, Modal, Segmented, Select, Skeleton, Tag,
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useSession } from '../session/SessionContext';
import {
  useAddTeacher, useAllTeachers, useSchools, useTeacherNorms, useTeachers,
} from '../api/queries';
import { PageHead, fmtN } from '../components/common';
import SearchInput from '../components/SearchInput';
import ServerTable from '../components/ServerTable';
import { colors } from '../theme';

const shortName = (name) => name.replace(/^МБОУ «|»$/g, '');
const fmtShare = (v) => (v == null ? '—' : v.toFixed(2).replace('.', ','));
const fmtD = (d) => dayjs(d).format('D MMM YYYY');

function TeacherCard({ schoolId, teacher, canAnalytics }) {
  const navigate = useNavigate();
  const norms = useTeacherNorms(schoolId, teacher.id);
  const n = teacher.current_norm;
  return (
    <Card className="side-card" aria-label="Карточка педагога">
      <div className="muted" style={{ fontSize: 13 }}><code className="code">{teacher.external_id}</code></div>
      <h2 className="side-card-title">{teacher.full_name ?? teacher.external_id}</h2>
      <div className="muted" style={{ fontSize: 14 }}>{teacher.subject}</div>

      <div className="mini-kpis">
        <div><div className="muted">По договору</div><b style={{ color: colors.planText }}>{fmtN(n?.contract_teaching_hours_per_week)}</b> <span className="muted">уч.ч/нед</span></div>
        <div><div className="muted">Доля ставки</div><b>{fmtShare(n?.rate_fraction)}</b></div>
      </div>

      <h3 className="side-card-h3">История норм</h3>
      {norms.isPending ? <Skeleton active title={false} paragraph={{ rows: 2 }} /> : (
        norms.data?.length ? norms.data.map((x) => {
          const current = !x.effective_to;
          return (
            <div key={x.id} className={`norm-item${current ? ' norm-item--current' : ''}`}>
              <div style={{ fontWeight: 500 }}>{current ? `с ${fmtD(x.effective_from)} · действует` : `${fmtD(x.effective_from)} — ${fmtD(x.effective_to)}`}</div>
              <div className="muted" style={{ fontSize: 13 }}>
                {fmtN(Number(x.contract_teaching_hours_per_week))} уч.ч/нед · норма {fmtN(Number(x.standard_teaching_hours_per_rate))}
                {x.plan_source ? ` · ${x.plan_source}` : ''}
              </div>
            </div>
          );
        }) : <div className="muted">Норм пока нет</div>
      )}

      <div className="side-card-note">
        Учётная запись: {teacher.has_account ? <b>связана</b> : 'не связана'}. Связь задаёт администратор в разделе «Пользователи и права».
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Button onClick={() => navigate(`/workload/plans?teacher=${teacher.id}`)}>Открыть план</Button>
        {canAnalytics && <Button onClick={() => navigate(`/analytics/teachers/${teacher.id}`)}>Аналитика</Button>}
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 10 }}>Нормы меняются импортом Excel на странице «Управление планом».</div>
    </Card>
  );
}

function AddTeacherModal({ open, schoolId, subjects, onClose }) {
  const [form] = Form.useForm();
  const { message } = App.useApp();
  const add = useAddTeacher(schoolId);
  return (
    <Modal
      open={open}
      title="Новый педагог"
      okText="Добавить"
      cancelText="Отмена"
      confirmLoading={add.isPending}
      onCancel={onClose}
      destroyOnHidden
      onOk={async () => {
        const v = await form.validateFields();
        try {
          await add.mutateAsync({ ...v, full_name: v.full_name.trim() });
          message.success('Педагог добавлен');
          onClose();
        } catch (e) {
          message.error(e.message);
        }
      }}
    >
      <Form form={form} layout="vertical" requiredMark={false} preserve={false}>
        <Form.Item name="full_name" label="ФИО" rules={[{ required: true, whitespace: true, message: 'Укажите ФИО' }]}>
          <Input maxLength={255} placeholder="Фамилия Имя Отчество" />
        </Form.Item>
        <Form.Item name="external_id" label="Код в школе" extra="Как в колонке «ID учителя» в Excel-файлах" rules={[{ required: true, whitespace: true, message: 'Укажите код' }]}>
          <Input maxLength={64} placeholder="например, T007" />
        </Form.Item>
        <Form.Item name="subject" label="Предмет" rules={[{ required: true, whitespace: true, message: 'Укажите предмет' }]}>
          <AutoComplete
            placeholder="Выберите или введите"
            options={subjects.map((x) => ({ value: x }))}
            filterOption={(input, o) => o.value.toLowerCase().includes(input.toLowerCase())}
          />
        </Form.Item>
      </Form>
      <div className="muted" style={{ fontSize: 13 }}>Норму нагрузки задаёт импорт Excel. Учётную запись связывает администратор.</div>
    </Modal>
  );
}

export default function Schools() {
  const { school, setSchoolId, role } = useSession();
  const schoolsQ = useSchools();
  const [q, setQ] = useState('');
  const [subject, setSubject] = useState();
  const [status, setStatus] = useState('active');
  const [pg, setPg] = useState({ page: 1, pageSize: 20 });
  const [selected, setSelected] = useState(null);
  const [adding, setAdding] = useState(false);

  const params = { q, subject, onlyActive: status === 'active', ...pg };
  const teachers = useTeachers(school?.id, params);
  const all = useAllTeachers(school?.id);
  const subjects = useMemo(() => [...new Set((all.data?.items ?? []).map((t) => t.subject))].sort(), [all.data]);
  const canAnalytics = role === 'head' || role === 'group_head';
  const wide = Grid.useBreakpoint().xl;

  const resetPage = () => setPg((p) => ({ ...p, page: 1 }));
  const pickSchool = (id) => { setSchoolId(id); setSelected(null); resetPage(); };

  const columns = [
    { title: 'Преподаватель', dataIndex: 'full_name', render: (v, t) => <Button type="link" style={{ padding: 0, height: 'auto' }} onClick={() => setSelected(t)}>{v ?? t.external_id}</Button> },
    { title: 'Код', dataIndex: 'external_id', render: (v) => <code className="code">{v}</code> },
    { title: 'Предмет', dataIndex: 'subject', render: (v) => <span className="muted">{v}</span> },
    { title: 'Договор, уч.ч/нед', key: 'contract', align: 'right', render: (_, t) => <b className="num" style={{ color: colors.planText }}>{fmtN(t.current_norm?.contract_teaching_hours_per_week)}</b> },
    { title: 'Норма за ставку', key: 'rate', align: 'right', render: (_, t) => fmtN(t.current_norm?.standard_teaching_hours_per_rate) },
    { title: 'Доля ставки', key: 'share', align: 'right', render: (_, t) => fmtShare(t.current_norm?.rate_fraction) },
    { title: 'Учётная запись', dataIndex: 'has_account', render: (v) => (v ? <Tag bordered={false} className="tag-ok">связана</Tag> : <span className="muted">нет</span>) },
    ...(status === 'all' ? [{ title: 'Статус', dataIndex: 'is_active', render: (v) => (v ? 'работает' : <span className="muted">не работает</span>) }] : []),
  ];

  return (
    <div className="page">
      <PageHead
        title="Школы и педагоги"
        sub="Состав школ и установленные нормы. Факт и опросы здесь не показываются."
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setAdding(true)}>Добавить педагога</Button>}
      />

      <div className="school-cards">
        {schoolsQ.isPending
          ? [0, 1].map((i) => <Card key={i}><Skeleton active title={{ width: 220 }} paragraph={{ rows: 1 }} /></Card>)
          : schoolsQ.data.map((s) => (
            <button key={s.id} type="button" aria-pressed={s.id === school?.id} className={`school-card${s.id === school?.id ? ' school-card--on' : ''}`} onClick={() => pickSchool(s.id)}>
              <span className="school-card-head">
                <span style={{ fontWeight: 600 }}>{shortName(s.name)}</span>
                <code className="code">{s.external_code}</code>
              </span>
              <span className="school-card-stats">
                <span><b>{s.teacher_count}</b> педагогов</span>
                <span><b>{s.linked_accounts}</b> с учётной записью</span>
                <span>директор: {s.director_name ?? 'не назначен'}</span>
              </span>
            </button>
          ))}
      </div>

      <div className="with-aside">
        <Card title={`Педагоги · ${school ? shortName(school.name) : ''}`} style={{ minWidth: 0 }}>
          <div className="filter-bar" style={{ marginBottom: 12 }}>
            <SearchInput value={q} onSearch={(v) => { setQ(v); resetPage(); }} placeholder="ФИО или предмет" style={{ width: 260, maxWidth: '100%' }} />
            <Select
              allowClear
              placeholder="Все предметы"
              aria-label="Предмет"
              value={subject}
              style={{ minWidth: 200 }}
              options={subjects.map((s) => ({ value: s, label: s }))}
              onChange={(v) => { setSubject(v); resetPage(); }}
            />
            <Segmented
              aria-label="Статус"
              value={status}
              onChange={(v) => { setStatus(v); resetPage(); }}
              options={[{ value: 'active', label: 'Работают' }, { value: 'all', label: 'Все' }]}
            />
          </div>
          <ServerTable
            query={teachers}
            columns={columns}
            page={pg.page}
            pageSize={pg.pageSize}
            onPageChange={(page, pageSize) => setPg({ page, pageSize })}
            size="middle"
            rowClassName={(t) => (t.id === selected?.id ? 'row-selected' : '')}
            onRow={(t) => ({ onClick: () => setSelected(t), style: { cursor: 'pointer' } })}
            locale={{ emptyText: q || subject ? 'Никого не нашли' : 'В школе пока нет педагогов' }}
          />
        </Card>

        {wide && (selected
          ? <TeacherCard key={selected.id} schoolId={school?.id} teacher={selected} canAnalytics={canAnalytics} />
          : <Card className="side-card"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Выберите педагога, чтобы увидеть нормы" /></Card>)}
      </div>

      {!wide && (
        <Drawer open={Boolean(selected)} onClose={() => setSelected(null)} placement="bottom" height="85%" title="Карточка педагога" styles={{ body: { padding: 0 } }}>
          {selected && <TeacherCard key={selected.id} schoolId={school?.id} teacher={selected} canAnalytics={canAnalytics} />}
        </Drawer>
      )}

      <AddTeacherModal open={adding} schoolId={school?.id} subjects={subjects} onClose={() => setAdding(false)} />
    </div>
  );
}
