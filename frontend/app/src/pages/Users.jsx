import { useEffect, useMemo, useState } from 'react';
import dayjs from 'dayjs';
import {
  App, Button, Card, Drawer, Empty, Form, Grid, Input, Modal, Select, Skeleton, Tag,
} from 'antd';
import { CheckOutlined, MinusOutlined, PlusOutlined } from '@ant-design/icons';
import { useSession, ROLE_LABELS } from '../session/SessionContext';
import {
  useAdminDirectory, useAdminMutations, useAdminUsers, useUserAudit,
} from '../api/queries';
import { PageHead } from '../components/common';
import SearchInput from '../components/SearchInput';
import ServerTable from '../components/ServerTable';

const ROLES = ['teacher', 'director', 'head', 'group_head', 'system_admin'];
const shortName = (name) => name.replace(/^МБОУ «|»$/g, '').replace(/ — .*/, '');

function effectiveRights(role, scope) {
  const yes = (text) => ({ ok: true, text });
  const no = (text) => ({ ok: false, text });
  switch (role) {
    case 'teacher': return [
      yes(`Свой план, ввод своей фактической нагрузки${scope ? ` — ${scope}` : ''}`),
      yes('Свои опросы и их тексты, своя аналитика'),
      no('Данные других преподавателей'),
    ];
    case 'director': return [
      yes(`План, нормы и импорт Excel${scope ? ` — ${scope}` : ''}`),
      yes('Плановый дашборд и отчёты по плану'),
      no('Фактическая нагрузка и самочувствие педагогов'),
      no('Изменение справочника видов работ'),
    ];
    case 'head':
    case 'group_head': return [
      yes(`План, нормы и импорт Excel${scope ? ` — ${scope}` : ''}`),
      yes('Фактическая нагрузка педагогов этих школ'),
      yes('Оценки анкет по шкалам и обобщённые показатели'),
      yes('ML-выгрузка без имён, журнал аудита, справочник видов работ'),
      no('Тексты комментариев к анкетам — только автор'),
      no('Данные других школ'),
    ];
    case 'system_admin': return [
      yes('Пользователи, роли и назначения'),
      yes('Справочник видов работ'),
      no('Содержимое анкет и данные нагрузки'),
    ];
    default: return [no('Роль не назначена — вход без доступа к данным')];
  }
}

function AccessEditor({ user, directory, currentUserId }) {
  const { message, modal } = App.useApp();
  const { setAccess, block } = useAdminMutations();
  const audit = useUserAudit(user.id);
  const [role, setRole] = useState(user.role);
  const [schoolIds, setSchoolIds] = useState(user.school_ids);
  const [groupIds, setGroupIds] = useState(user.group_ids);
  const [teacherId, setTeacherId] = useState(user.teacher?.id);

  const schoolOptions = directory.schools.map((s) => ({ value: s.id, label: shortName(s.name) }));
  const singleSchool = role === 'teacher' || role === 'director';
  const teacherOptions = (directory.schools.find((s) => s.id === schoolIds[0])?.teachers ?? []).map((t) => ({
    value: t.id,
    label: t.user_id && t.user_id !== user.id ? `${t.full_name} — связан с другой учётной записью` : t.full_name,
    disabled: Boolean(t.user_id && t.user_id !== user.id),
  }));

  const scopeLabel = role === 'group_head'
    ? directory.groups.filter((g) => groupIds.includes(g.id)).map((g) => g.name).join(', ')
    : schoolIds.map((id) => schoolOptions.find((o) => o.value === id)?.label ?? id).join(', ');

  const pickRole = (r) => {
    setRole(r);
    if ((r === 'teacher' || r === 'director') && schoolIds.length > 1) setSchoolIds(schoolIds.slice(0, 1));
    if (r !== 'teacher') setTeacherId(undefined);
  };

  const save = async () => {
    try {
      await setAccess.mutateAsync({
        userId: user.id,
        body: { role, school_ids: role === 'group_head' ? [] : schoolIds, group_ids: role === 'group_head' ? groupIds : [], teacher_id: role === 'teacher' ? teacherId : null },
      });
      message.success('Права сохранены');
    } catch (e) {
      message.error(e.message);
    }
  };

  const toggleBlock = () => modal.confirm({
    title: user.is_active ? `Заблокировать вход для «${user.name}»?` : `Разблокировать вход для «${user.name}»?`,
    content: user.is_active ? 'Пользователь не сможет войти. Его данные и назначения сохранятся.' : 'Пользователь снова сможет войти с прежними правами.',
    okText: user.is_active ? 'Заблокировать' : 'Разблокировать',
    okButtonProps: user.is_active ? { danger: true } : undefined,
    cancelText: 'Отмена',
    onOk: () => block.mutateAsync({ userId: user.id, unblock: !user.is_active }).catch((e) => message.error(e.message)),
  });

  return (
    <Card className="side-card" aria-label="Назначение прав">
      <code className="code">{user.login}</code>
      <h2 className="side-card-title">{user.name}</h2>
      {!user.is_active && <Tag bordered={false} style={{ marginBottom: 8 }}>вход заблокирован</Tag>}

      <fieldset className="plain-fieldset">
        <legend>Роль</legend>
        <div className="chips">
          {ROLES.map((r) => (
            <button key={r} type="button" aria-pressed={r === role} className={`chip${r === role ? ' chip--on' : ''}`} onClick={() => pickRole(r)}>
              {ROLE_LABELS[r]}
            </button>
          ))}
        </div>
      </fieldset>

      {role && role !== 'system_admin' && (
        <div className="side-field">
          <div className="side-field-label">
            {role === 'group_head' ? 'Группы школ' : role === 'head' ? 'Школы главы' : 'Школа'}
          </div>
          {role === 'group_head' ? (
            <Select mode="multiple" value={groupIds} onChange={setGroupIds} style={{ width: '100%' }} placeholder="Выберите группы" options={directory.groups.map((g) => ({ value: g.id, label: g.name }))} />
          ) : (
            <Select
              mode={singleSchool ? undefined : 'multiple'}
              value={singleSchool ? schoolIds[0] : schoolIds}
              onChange={(v) => { setSchoolIds(singleSchool ? [v] : v); if (singleSchool) setTeacherId(undefined); }}
              style={{ width: '100%' }}
              placeholder="Выберите школу"
              options={schoolOptions}
            />
          )}
          {role === 'teacher' && (
            <>
              <div className="side-field-label" style={{ marginTop: 10 }}>Карточка педагога</div>
              <Select
                showSearch
                optionFilterProp="label"
                value={teacherId}
                onChange={setTeacherId}
                disabled={!schoolIds[0]}
                style={{ width: '100%' }}
                placeholder="С кем связать учётную запись"
                options={teacherOptions}
              />
            </>
          )}
          <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>Директору — одна школа, главе — набор школ, главе группы — группы, преподавателю — школа и карточка.</div>
        </div>
      )}

      <div className="rights-preview">
        <div className="report-info-title">Что будет доступно</div>
        {effectiveRights(role, scopeLabel).map((r) => (
          <div key={r.text} className={`right-line${r.ok ? '' : ' right-line--no'}`}>
            {r.ok ? <CheckOutlined aria-label="доступно" /> : <MinusOutlined aria-label="недоступно" />}
            <span>{r.text}</span>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Button type="primary" loading={setAccess.isPending} disabled={!role} onClick={save}>Сохранить</Button>
        {user.id !== currentUserId && (
          <Button danger={user.is_active} loading={block.isPending} onClick={toggleBlock}>{user.is_active ? 'Заблокировать вход' : 'Разблокировать'}</Button>
        )}
      </div>

      <div className="side-card-section">
        <div className="report-info-title">Журнал назначений</div>
        {audit.isPending ? <Skeleton active title={false} paragraph={{ rows: 2 }} /> : (
          audit.data.length
            ? audit.data.map((a) => (
              <div key={a.id} style={{ fontSize: 13, lineHeight: 1.4, marginBottom: 6 }}>
                <span className="muted">{dayjs(a.at).format('D MMM YYYY, HH:mm')}</span> · {a.text} <span className="muted">— {a.actor}</span>
              </div>
            ))
            : <div className="muted" style={{ fontSize: 13 }}>Изменений пока не было</div>
        )}
      </div>
    </Card>
  );
}

function InviteModal({ open, onClose, onCreated }) {
  const [form] = Form.useForm();
  const { message } = App.useApp();
  const { create } = useAdminMutations();
  return (
    <Modal
      open={open}
      title="Новый пользователь"
      okText="Создать"
      cancelText="Отмена"
      confirmLoading={create.isPending}
      onCancel={onClose}
      destroyOnHidden
      onOk={async () => {
        const v = await form.validateFields();
        try {
          const u = await create.mutateAsync(v);
          message.success('Учётная запись создана — назначьте роль');
          onCreated(u);
        } catch (e) {
          message.error(e.message);
        }
      }}
    >
      <Form form={form} layout="vertical" requiredMark={false} preserve={false}>
        <Form.Item name="name" label="Имя" rules={[{ required: true, whitespace: true, message: 'Укажите имя' }]}>
          <Input maxLength={255} placeholder="Фамилия Имя Отчество" />
        </Form.Item>
        <Form.Item name="login" label="Логин" rules={[{ required: true, whitespace: true, message: 'Укажите логин' }]}>
          <Input maxLength={64} autoComplete="off" />
        </Form.Item>
      </Form>
      <div className="muted" style={{ fontSize: 13 }}>Пароль пользователь задаст сам при первом входе.</div>
    </Modal>
  );
}

export default function Users() {
  const { user: me } = useSession();
  const [q, setQ] = useState('');
  const [role, setRole] = useState();
  const [status, setStatus] = useState();
  const [pg, setPg] = useState({ page: 1, pageSize: 20 });
  const [selectedId, setSelectedId] = useState(null);
  const [inviting, setInviting] = useState(false);

  const users = useAdminUsers({ q, role, status, ...pg });
  const directory = useAdminDirectory();
  const selected = useMemo(() => users.data?.items.find((u) => u.id === selectedId) ?? null, [users.data, selectedId]);
  useEffect(() => { if (selectedId && users.data && !selected && !users.isPlaceholderData) setSelectedId(null); }, [selectedId, selected, users.data, users.isPlaceholderData]);

  const resetPage = () => setPg((p) => ({ ...p, page: 1 }));
  const wide = Grid.useBreakpoint().xl;

  const columns = [
    {
      title: 'Пользователь', dataIndex: 'name',
      render: (v, u) => <><div style={{ fontWeight: 500 }}>{v}</div><code className="code">{u.login}</code></>,
    },
    { title: 'Роль', dataIndex: 'role', render: (v) => (v ? <span className={`role-tag role-${v}`}>{ROLE_LABELS[v]}</span> : <span className="muted">не назначена</span>) },
    { title: 'Область', dataIndex: 'scope_label', render: (v) => <span className="muted">{v}</span> },
    { title: 'Педагог', dataIndex: 'teacher', render: (v, u) => (v ? `${v.full_name}` : <span className="muted">{u.role === 'teacher' ? 'не связан' : '—'}</span>) },
    { title: 'Статус', dataIndex: 'is_active', render: (v) => (v ? <span style={{ color: '#166534' }}>активен</span> : <Tag bordered={false}>заблокирован</Tag>) },
  ];

  return (
    <div className="page">
      <PageHead
        title="Пользователи и права"
        sub="Права определяются только ролью и назначенными школами или группами. Индивидуальных разрешений нет."
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setInviting(true)}>Новый пользователь</Button>}
      />

      <div className="with-aside with-aside--wide">
        <Card style={{ minWidth: 0 }}>
          <div className="filter-bar" style={{ marginBottom: 12 }}>
            <SearchInput value={q} onSearch={(v) => { setQ(v); resetPage(); }} placeholder="Имя или логин" style={{ width: 260, maxWidth: '100%' }} />
            <Select
              allowClear
              placeholder="Все роли"
              aria-label="Роль"
              value={role}
              style={{ minWidth: 170 }}
              options={ROLES.map((r) => ({ value: r, label: ROLE_LABELS[r] }))}
              onChange={(v) => { setRole(v); resetPage(); }}
            />
            <Select
              allowClear
              placeholder="Любой статус"
              aria-label="Статус"
              value={status}
              style={{ minWidth: 170 }}
              options={[{ value: 'active', label: 'Активные' }, { value: 'blocked', label: 'Заблокированные' }]}
              onChange={(v) => { setStatus(v); resetPage(); }}
            />
          </div>
          <ServerTable
            query={users}
            columns={columns}
            page={pg.page}
            pageSize={pg.pageSize}
            onPageChange={(page, pageSize) => setPg({ page, pageSize })}
            size="middle"
            rowClassName={(u) => (u.id === selectedId ? 'row-selected' : '')}
            onRow={(u) => ({ onClick: () => setSelectedId(u.id), style: { cursor: 'pointer' } })}
            locale={{ emptyText: 'Никого не нашли' }}
          />
        </Card>

        {wide && (selected && directory.data
          ? <AccessEditor key={`${selected.id}-${selected.updated_at}`} user={selected} directory={directory.data} currentUserId={me.id} />
          : (
            <Card className="side-card">
              {selected ? <Skeleton active /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Выберите пользователя, чтобы назначить роль и область" />}
            </Card>
          ))}
      </div>

      {!wide && (
        <Drawer open={Boolean(selected)} onClose={() => setSelectedId(null)} placement="bottom" height="90%" title="Права пользователя" styles={{ body: { padding: 0 } }}>
          {selected && (directory.data
            ? <AccessEditor key={`${selected.id}-${selected.updated_at}`} user={selected} directory={directory.data} currentUserId={me.id} />
            : <Skeleton active style={{ padding: 16 }} />)}
        </Drawer>
      )}

      <InviteModal
        open={inviting}
        onClose={() => setInviting(false)}
        onCreated={(u) => { setInviting(false); setQ(''); setRole(undefined); setStatus(undefined); setSelectedId(u.id); }}
      />
    </div>
  );
}
