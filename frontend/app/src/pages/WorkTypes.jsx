import { useMemo, useState } from 'react';
import {
  App, Button, Card, Form, Input, InputNumber, Modal, Segmented, Select, Switch, Table, Tag,
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useSession } from '../session/SessionContext';
import { useWorkTypeMutations, useWorkTypes } from '../api/queries';
import { PageHead } from '../components/common';
import SearchInput from '../components/SearchInput';
import { TableSkeleton } from '../components/Skeletons';
import { colors } from '../theme';

const EDITORS = ['head', 'group_head', 'system_admin'];
const GROUP_LABELS = {
  teaching: 'Учебная работа',
  teaching_support: 'Подготовка и проверка',
  administrative: 'Документы',
  communication: 'Общение',
  student_support: 'Классное руководство',
  professional_development: 'Совещания и методика',
  other: 'Прочее',
};
const fmtW = (v) => Number(v).toFixed(2).replace('.', ',');

function WeightChip({ value, max }) {
  const i = max > 0 ? Math.min(4, Math.floor((Number(value) / max) * 4.999)) : 0;
  return (
    <span className="weight-chip" style={{ background: Number(value) ? colors.scale[i] : '#EEF1F0', color: i >= 3 ? '#fff' : colors.text }}>
      {fmtW(value)}
    </span>
  );
}

function WorkTypeModal({ open, initial, onClose, onSave, saving }) {
  const [form] = Form.useForm();
  const isNew = !initial?.id;
  return (
    <Modal
      open={open}
      title={isNew ? 'Новая категория' : `Изменить: ${initial.name}`}
      okText="Сохранить"
      cancelText="Отмена"
      confirmLoading={saving}
      onCancel={onClose}
      destroyOnHidden
      afterOpenChange={(o) => o && form.setFieldsValue(initial ?? { complexity_weight: 0, requires_comment: false })}
      onOk={async () => onSave(await form.validateFields())}
    >
      <Form form={form} layout="vertical" requiredMark={false} preserve={false}>
        <Form.Item
          name="code"
          label="Код"
          extra="Латиница в нижнем регистре, цифры, «_» и «-». После создания не меняется."
          rules={[{ required: true, message: 'Укажите код' }, { pattern: /^[a-z0-9_-]+$/, message: 'Только a–z, 0–9, «_» и «-»' }]}
        >
          <Input disabled={!isNew} maxLength={80} placeholder="например, olympiad_prep" />
        </Form.Item>
        <Form.Item name="name" label="Название" rules={[{ required: true, whitespace: true, message: 'Укажите название' }]}>
          <Input maxLength={255} />
        </Form.Item>
        <Form.Item name="category_group" label="Группа" rules={[{ required: true, message: 'Выберите группу' }]}>
          <Select options={Object.entries(GROUP_LABELS).map(([value, label]) => ({ value, label }))} />
        </Form.Item>
        <Form.Item
          name="complexity_weight"
          label="Вес сложности"
          extra="От 0 до 1. Сумма весов активных категорий должна быть 1."
          rules={[{ required: true, message: 'Укажите вес' }]}
        >
          <InputNumber min={0} max={1} step={0.01} precision={2} decimalSeparator="," style={{ width: 140 }} />
        </Form.Item>
        <Form.Item name="requires_comment" label="Комментарий при вводе обязателен" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name="description" label="Описание">
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default function WorkTypes() {
  const { role } = useSession();
  const { message, modal } = App.useApp();
  const canEdit = EDITORS.includes(role);
  const [status, setStatus] = useState('active');
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState(null);
  const all = useWorkTypes({ includeArchived: true });
  const { save, archive, restore } = useWorkTypeMutations();

  const active = useMemo(() => (all.data ?? []).filter((w) => w.is_active), [all.data]);
  const weightSum = active.reduce((s, w) => s + Number(w.complexity_weight), 0);
  const maxWeight = Math.max(0, ...active.map((w) => Number(w.complexity_weight)));
  const sumOk = Math.abs(weightSum - 1) < 0.005;

  const rows = useMemo(() => {
    const q = search.toLowerCase();
    return (all.data ?? [])
      .filter((w) => (status === 'active' ? w.is_active : !w.is_active))
      .filter((w) => !q || w.name.toLowerCase().includes(q) || w.code.includes(q));
  }, [all.data, status, search]);

  const onSave = async (values) => {
    try {
      const { code, ...rest } = values;
      await save.mutateAsync(editing.id ? { id: editing.id, body: rest } : { body: values });
      message.success('Сохранено');
      setEditing(null);
    } catch (e) {
      message.error(e.message);
    }
  };

  const onArchive = (w) => modal.confirm({
    title: `Перенести «${w.name}» в архив?`,
    content: 'Категория пропадёт из выбора при вводе. Уже внесённые данные сохранятся.',
    okText: 'В архив',
    cancelText: 'Отмена',
    onOk: () => archive.mutateAsync(w.id).then(() => message.success('Перенесено в архив'), (e) => message.error(e.message)),
  });

  const columns = [
    { title: 'Код', dataIndex: 'code', render: (v) => <code className="code">{v}</code> },
    { title: 'Название', dataIndex: 'name', render: (v) => <span style={{ fontWeight: 500 }}>{v}</span> },
    { title: 'Группа', dataIndex: 'category_group', render: (v) => <span className="muted">{GROUP_LABELS[v] ?? v}</span> },
    { title: 'Вес сложности', dataIndex: 'complexity_weight', align: 'right', render: (v) => <WeightChip value={v} max={maxWeight} /> },
    { title: 'Комментарий', dataIndex: 'requires_comment', render: (v) => (v ? <Tag bordered={false}>обязателен</Tag> : <span className="muted">нет</span>) },
    ...(canEdit ? [{
      title: <span className="sr-only">Действия</span>,
      key: 'actions',
      align: 'right',
      render: (_, w) => (
        <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
          <Button size="small" onClick={() => setEditing(w)}>Изменить</Button>
          {w.is_active
            ? <Button size="small" type="text" onClick={() => onArchive(w)}>В архив</Button>
            : <Button size="small" type="text" onClick={() => restore.mutateAsync(w.id).catch((e) => message.error(e.message))}>Вернуть</Button>}
        </div>
      ),
    }] : []),
  ];

  return (
    <div className="page">
      <PageHead
        title="Виды работ"
        sub="Справочник категорий для плана и факта. Учитель выбирает из него при вводе внеплановой работы."
        extra={canEdit && <Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing({})}>Новая категория</Button>}
      />

      <div className={`info-banner${sumOk ? '' : ' info-banner--warn'}`}>
        <strong>Вес сложности — доля категории в общей сложности работы.</strong>
        <span>
          Сумма весов активных категорий: <b className="num">{fmtW(weightSum)}</b>
          {sumOk ? ' — сходится.' : ' — должна быть 1,00, поправьте веса.'} Значения — гипотеза, уточним по реальным данным.
        </span>
      </div>

      <Card>
        <div className="filter-bar" style={{ marginBottom: 12 }}>
          <SearchInput value={search} onSearch={setSearch} placeholder="Поиск по названию или коду" style={{ width: 280, maxWidth: '100%' }} />
          <Segmented
            aria-label="Статус"
            value={status}
            onChange={setStatus}
            options={[{ value: 'active', label: 'Активные' }, { value: 'archived', label: 'Архив' }]}
          />
          {!canEdit && <span className="muted" style={{ fontSize: 13 }}>Изменять справочник могут глава и глава группы</span>}
        </div>
        {all.isPending ? <TableSkeleton rows={9} /> : (
          <Table
            rowKey="id"
            dataSource={rows}
            columns={columns}
            pagination={false}
            scroll={{ x: 720 }}
            size="middle"
            locale={{ emptyText: search ? 'Ничего не найдено' : 'Пусто' }}
          />
        )}
        <div className="muted" style={{ fontSize: 13, marginTop: 10 }}>Категорию, которая уже есть в данных, нельзя удалить — только перенести в архив.</div>
      </Card>

      <WorkTypeModal
        open={editing !== null}
        initial={editing}
        saving={save.isPending}
        onClose={() => setEditing(null)}
        onSave={onSave}
      />
    </div>
  );
}
