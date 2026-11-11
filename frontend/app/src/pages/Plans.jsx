import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import dayjs from 'dayjs';
import {
  Alert, App, Button, Card, DatePicker, Segmented, Select, Table, Tag, Upload,
} from 'antd';
import {
  CheckCircleFilled, DownloadOutlined, FileExcelOutlined, UploadOutlined,
} from '@ant-design/icons';
import { useSession } from '../session/SessionContext';
import {
  useAllTeachers, useImportMutations, useImports, usePlanItems, useWorkTypes,
} from '../api/queries';
import { filesApi } from '../api/endpoints';
import { download } from '../api/download';
import { PageHead, fmtH } from '../components/common';
import ServerTable from '../components/ServerTable';
import { colors } from '../theme';

const ACADEMIC_HOUR = 0.75;
const fmtDate = (d) => d.format('YYYY-MM-DD');

function ImportPanel({ schoolId, onDone }) {
  const { message } = App.useApp();
  const [file, setFile] = useState(null);
  const [effectiveFrom, setEffectiveFrom] = useState(dayjs().startOf('isoWeek'));
  const [mode, setMode] = useState('insert_only');
  const { validate, commit } = useImportMutations(schoolId);

  const form = (f = file) => {
    const fd = new FormData();
    fd.append('file', f);
    fd.append('effective_from', fmtDate(effectiveFrom));
    fd.append('mode', mode);
    return fd;
  };

  const check = (f) => {
    setFile(f);
    validate.reset();
    commit.reset();
    validate.mutate(form(f));
  };

  const report = validate.data;
  const step = !file ? 0 : validate.isPending ? 1 : report ? (commit.isSuccess ? 4 : 3) : 1;
  const steps = ['Файл загружен', 'Структура и типы проверены', 'Проверка строк', 'Подтверждение'];

  const confirm = async () => {
    try {
      await commit.mutateAsync(form());
      message.success('План загружен');
      onDone();
    } catch (e) {
      message.error(e.message);
    }
  };

  return (
    <Card style={{ marginBottom: 16 }}>
      <div className="import-params">
        <Upload
          accept=".xlsx"
          maxCount={1}
          showUploadList={false}
          beforeUpload={(f) => { check(f); return false; }}
        >
          <Button type="primary" icon={<UploadOutlined />}>{file ? 'Выбрать другой файл' : 'Выбрать Excel-файл'}</Button>
        </Upload>
        <label className="inline-field">
          <span>Действует с</span>
          <DatePicker value={effectiveFrom} onChange={(d) => d && setEffectiveFrom(d)} format="D MMM YYYY" allowClear={false} />
        </label>
        <label className="inline-field">
          <span>Режим</span>
          <Segmented
            value={mode}
            onChange={setMode}
            options={[{ value: 'insert_only', label: 'Только новые' }, { value: 'upsert', label: 'Новые и обновить' }]}
          />
        </label>
      </div>

      {file && (
        <>
          <ol className="import-steps">
            {steps.map((s, i) => (
              <li key={s} className={i < step ? 'done' : i === step ? 'current' : ''}>
                {i < step ? <CheckCircleFilled aria-hidden /> : <span className="step-num">{i + 1}</span>} {s}
              </li>
            ))}
          </ol>

          <div className="import-file">
            <div className="file-badge"><FileExcelOutlined /></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 500, overflowWrap: 'anywhere' }}>{file.name}</div>
              <div className="muted" style={{ fontSize: 13 }}>
                {report ? `${report.summary.teachers} педагогов · ${report.summary.daily_plans} строк плана · шаблон ${report.template_version}` : 'Проверяем…'}
              </div>
            </div>
            {report && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <Tag bordered={false} className="tag-ok">{report.summary.to_create} к добавлению</Tag>
                {report.errors.length > 0 && <Tag bordered={false} className="tag-err">{report.errors.length} с ошибками</Tag>}
              </div>
            )}
          </div>

          {validate.isError && <Alert type="error" showIcon message={validate.error.message} style={{ marginTop: 12 }} />}

          {report?.errors.length > 0 && (
            <Table
              className="errors-table"
              size="small"
              rowKey={(e, i) => `${e.sheet}-${e.row}-${i}`}
              dataSource={report.errors}
              pagination={report.errors.length > 10 ? { pageSize: 10 } : false}
              scroll={{ x: 720 }}
              columns={[
                { title: 'Лист', dataIndex: 'sheet' },
                { title: 'Строка', dataIndex: 'row', render: (v) => <b>{v ?? '—'}</b> },
                { title: 'Поле', dataIndex: 'field' },
                { title: 'Ошибка', dataIndex: 'message', render: (v) => <span style={{ color: colors.error }}>{v}</span> },
              ]}
            />
          )}
          {report?.warnings?.length > 0 && (
            <ul className="import-warnings">
              {report.warnings.map((w, i) => <li key={i}>{w.sheet}{w.row ? `, строка ${w.row}` : ''}: {w.message}</li>)}
            </ul>
          )}

          {report && !commit.isSuccess && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12, alignItems: 'center' }}>
              <Button type="primary" disabled={!report.valid} loading={commit.isPending} onClick={confirm}>Подтвердить импорт</Button>
              {!report.valid && <span className="muted" style={{ fontSize: 14 }}>Исправьте ошибки в файле и загрузите его снова</span>}
            </div>
          )}
          {commit.isSuccess && <Alert type="success" showIcon message={`Загружено строк: ${commit.data.rows_created}, обновлено: ${commit.data.rows_updated}`} style={{ marginTop: 12 }} />}
        </>
      )}
    </Card>
  );
}

export default function Plans() {
  const { school } = useSession();
  const { message } = App.useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const teacherId = searchParams.get('teacher') ?? undefined;
  const [workTypeId, setWorkTypeId] = useState();
  const [range, setRange] = useState(() => {
    const s = dayjs().startOf('isoWeek');
    return [s, s.add(6, 'day')];
  });
  const [pg, setPg] = useState({ page: 1, pageSize: 20 });
  const [histPg, setHistPg] = useState({ page: 1, pageSize: 20 });
  const [importOpen, setImportOpen] = useState(false);

  const teachersQ = useAllTeachers(school?.id);
  const workTypesQ = useWorkTypes();
  const params = { teacherId, workTypeId, dateFrom: fmtDate(range[0]), dateTo: fmtDate(range[1]), ...pg };
  const items = usePlanItems(school?.id, params);
  const imports = useImports(school?.id, histPg);

  const teacherName = useMemo(() => Object.fromEntries((teachersQ.data?.items ?? []).map((t) => [t.id, t.full_name ?? t.external_id])), [teachersQ.data]);
  const wt = useMemo(() => Object.fromEntries((workTypesQ.data ?? []).map((w) => [w.id, w])), [workTypesQ.data]);

  const setFilter = (fn) => { fn(); setPg((p) => ({ ...p, page: 1 })); };

  const columns = [
    { title: 'Дата', dataIndex: 'work_date', render: (v) => <span className="muted">{dayjs(v).format('dd D.MM')}</span> },
    { title: 'Преподаватель', dataIndex: 'teacher_id', render: (v) => teacherName[v] ?? v },
    { title: 'Вид работы', dataIndex: 'work_type_id', render: (v) => wt[v]?.name ?? v },
    {
      title: 'Уроки, уч.ч', key: 'lessons', align: 'right',
      render: (_, r) => (wt[r.work_type_id]?.category_group === 'teaching' ? Math.round(Number(r.duration_hours) / ACADEMIC_HOUR) : <span className="muted">—</span>),
    },
    { title: 'Астр.ч', dataIndex: 'duration_hours', align: 'right', render: (v) => <span className="num" style={{ color: colors.planText, fontWeight: 600 }}>{fmtH(Number(v))}</span> },
    { title: 'Версия', key: 'ver', render: (_, r) => <span className="muted" style={{ fontSize: 13 }}>v{r.plan_version ?? '?'}{r.source_import_filename ? ` · ${r.source_import_filename}` : ''}</span> },
  ];

  const importColumns = [
    { title: 'Дата', dataIndex: 'imported_at', render: (v) => <span className="muted">{v ? dayjs(v).format('D.MM.YYYY HH:mm') : '—'}</span> },
    { title: 'Пользователь', dataIndex: 'created_by_name', render: (v) => v ?? '—' },
    {
      title: 'Файл', dataIndex: 'original_filename',
      render: (v, r) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => download(() => filesApi.importFile(school.id, r.id), v, message)}>{v}</Button>
      ),
    },
    {
      title: 'Итог', key: 'result',
      render: (_, r) => (r.status === 'failed'
        ? <Tag bordered={false} className="tag-err">Ошибка</Tag>
        : r.rows_skipped > 0
          ? <Tag bordered={false} className="tag-partial">Частично</Tag>
          : <Tag bordered={false} className="tag-ok">Успешно</Tag>),
    },
    { title: 'Добавлено / обновлено / пропущено', key: 'counts', align: 'right', render: (_, r) => <span className="num">{r.rows_created} / {r.rows_updated} / {r.rows_skipped}</span> },
  ];

  return (
    <div className="page">
      <PageHead
        title="Управление планом"
        sub="Импорт норм и ежедневного плана из Excel, просмотр и экспорт"
        extra={(
          <>
            <Button icon={<DownloadOutlined />} onClick={() => download(() => filesApi.template(school.id), 'workload_template.xlsx', message)}>Скачать шаблон</Button>
            <Button type="primary" icon={<UploadOutlined />} onClick={() => setImportOpen((o) => !o)}>{importOpen ? 'Скрыть импорт' : 'Загрузить Excel'}</Button>
          </>
        )}
      />

      {importOpen && <ImportPanel schoolId={school?.id} onDone={() => setHistPg((p) => ({ ...p, page: 1 }))} />}

      <Card title="План" style={{ marginBottom: 16 }}>
        <div className="filter-bar" style={{ marginBottom: 12 }}>
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="Все преподаватели"
            aria-label="Преподаватель"
            value={teacherId}
            loading={teachersQ.isPending}
            style={{ minWidth: 220 }}
            options={(teachersQ.data?.items ?? []).map((t) => ({ value: t.id, label: t.full_name ?? t.external_id }))}
            onChange={(v) => setFilter(() => setSearchParams(v ? { teacher: v } : {}, { replace: true }))}
          />
          <Select
            allowClear
            placeholder="Все виды работ"
            aria-label="Вид работы"
            value={workTypeId}
            style={{ minWidth: 200 }}
            options={(workTypesQ.data ?? []).map((w) => ({ value: w.id, label: w.name }))}
            onChange={(v) => setFilter(() => setWorkTypeId(v))}
          />
          <DatePicker.RangePicker
            aria-label="Период"
            value={range}
            format="D MMM"
            allowClear={false}
            className="range-compact"
            onChange={(r) => r && setFilter(() => setRange(r))}
          />
          <div style={{ flex: 1 }} />
          <Button
            icon={<DownloadOutlined />}
            onClick={() => download(() => filesApi.export(school.id, { dateFrom: params.dateFrom, dateTo: params.dateTo, teacherId, report: 'planned' }), `plan_${params.dateFrom}_${params.dateTo}.xlsx`, message)}
          >
            Экспорт XLSX
          </Button>
        </div>
        <ServerTable
          query={items}
          columns={columns}
          page={pg.page}
          pageSize={pg.pageSize}
          onPageChange={(page, pageSize) => setPg({ page, pageSize })}
          size="middle"
          locale={{ emptyText: 'За выбранный период плана нет' }}
        />
        <div className="muted" style={{ fontSize: 13, marginTop: 10 }}>1 урок = 0,75 астр.ч</div>
      </Card>

      <Card title="История импортов">
        <ServerTable
          query={imports}
          columns={importColumns}
          page={histPg.page}
          pageSize={histPg.pageSize}
          onPageChange={(page, pageSize) => setHistPg({ page, pageSize })}
          size="middle"
          locale={{ emptyText: 'Импортов ещё не было' }}
        />
      </Card>
    </div>
  );
}
