import { useEffect, useMemo, useState } from 'react';
import dayjs from 'dayjs';
import { App, Button, Card, Input, Pagination, Skeleton } from 'antd';
import { useSession } from '../session/SessionContext';
import { useSaveSurveyResponse, useSurvey, useSurveyResponses } from '../api/queries';
import { PageHead } from '../components/common';
import { TableSkeleton } from '../components/Skeletons';
import { colors } from '../theme';

const SURVEY_CODE = 'daily_checkin';
const HISTORY_PAGE_SIZE = 10;
const fmtDate = (d) => d.format('YYYY-MM-DD');
const SCALE_FG = ['#145A50', '#145A50', '#0E3F38', '#FFFFFF', '#FFFFFF'];

function ScaleQuestion({ q, value, disabled, onChange }) {
  const min = q.min ?? 1;
  const max = q.max ?? 5;
  const values = Array.from({ length: max - min + 1 }, (_, i) => min + i);
  return (
    <fieldset className="survey-q">
      <legend>{q.title}{q.required && <span className="req" aria-hidden="true"> *</span>}</legend>
      <div className="scale-btns" role="radiogroup" aria-label={q.title}>
        {values.map((v, i) => {
          const on = value === v;
          return (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={on}
              disabled={disabled}
              className={`scale-btn${on ? ' scale-btn--on' : ''}`}
              style={on ? { background: colors.scale[i], color: SCALE_FG[i] } : undefined}
              onClick={() => onChange(v)}
            >
              {v}
            </button>
          );
        })}
      </div>
      {(q.labels?.[min] || q.labels?.[max]) && (
        <div className="scale-labels">
          <span>{q.labels?.[min] && `${min} — ${q.labels[min]}`}</span>
          <span>{q.labels?.[max] && `${max} — ${q.labels[max]}`}</span>
        </div>
      )}
    </fieldset>
  );
}

function ChoiceQuestion({ q, value, disabled, onChange }) {
  return (
    <fieldset className="survey-q">
      <legend>{q.title}{q.required && <span className="req" aria-hidden="true"> *</span>}</legend>
      <div className="chips" role="radiogroup" aria-label={q.title}>
        {q.options.map((o) => (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={value === o.value}
            disabled={disabled}
            className={`chip${value === o.value ? ' chip--on' : ''}`}
            onClick={() => onChange(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function TextQuestion({ q, value, disabled, onChange }) {
  const id = `q-${q.id}`;
  return (
    <div className="survey-q survey-q--last">
      <label htmlFor={id} className="survey-label">{q.title}{q.required && <span className="req" aria-hidden="true"> *</span>}</label>
      <Input.TextArea
        id={id}
        rows={4}
        value={value ?? ''}
        maxLength={q.max_length ?? 3000}
        showCount
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Несколько слов своими словами"
      />
      <div className="muted" style={{ fontSize: 13, marginTop: 6 }}>Текст видите только вы.</div>
    </div>
  );
}

function ScoreSquare({ value, title }) {
  if (value == null) return <span className="score-sq score-sq--empty" title={title}>—</span>;
  return <span className="score-sq" title={`${title}: ${value}`} style={{ background: colors.scale[value - 1], color: SCALE_FG[value - 1] }}>{value}</span>;
}

export default function DailySurvey() {
  const { school } = useSession();
  const { message } = App.useApp();
  const today = fmtDate(dayjs());
  const [date, setDate] = useState(today);
  const [answers, setAnswers] = useState({});
  const [historyPage, setHistoryPage] = useState(1);

  const survey = useSurvey(school?.id, SURVEY_CODE);
  const weekFrom = fmtDate(dayjs().subtract(6, 'day'));
  const recent = useSurveyResponses(school?.id, { surveyCode: SURVEY_CODE, dateFrom: weekFrom, dateTo: today, pageSize: 20 });
  const history = useSurveyResponses(school?.id, { surveyCode: SURVEY_CODE, page: historyPage, pageSize: HISTORY_PAGE_SIZE });
  const save = useSaveSurveyResponse(school?.id);

  const responseFor = (d) => recent.data?.items.find((r) => r.assessment_date === d && r.status !== 'withdrawn');
  const current = recent.data ? responseFor(date) ?? null : undefined;
  const submitted = current?.status === 'submitted';

  useEffect(() => {
    if (current === undefined) return;
    setAnswers(current?.answers ?? {});
  }, [date, current?.id, current?.lock_version, recent.isSuccess]);

  const questions = useMemo(() => survey.data?.questions ?? [], [survey.data]);
  const missing = questions.filter((q) => q.required && (answers[q.id] === undefined || String(answers[q.id]).trim() === ''));

  const chips = Array.from({ length: 7 }, (_, i) => {
    const d = dayjs().subtract(i, 'day');
    const r = responseFor(fmtDate(d));
    const state = r?.status === 'submitted' ? 'отправлено' : r?.status === 'draft' ? 'черновик' : 'не заполнено';
    return { date: fmtDate(d), label: i === 0 ? `Сегодня, ${d.format('D MMM')}` : `${d.format('D MMM')} · ${state}`, empty: !r };
  });

  const submit = async (send) => {
    if (send && missing.length) {
      message.warning(`Ответьте на обязательные вопросы: осталось ${missing.length}`);
      return;
    }
    const clean = Object.fromEntries(Object.entries(answers).filter(([, v]) => v !== undefined && v !== ''));
    try {
      await save.mutateAsync({
        responseId: current?.id,
        answers: clean,
        submit: send,
        create: {
          survey_code: SURVEY_CODE,
          survey_version: survey.data.version,
          assessment_date: date,
          period_start: date,
          period_end: date,
          comment_reference_date: date,
          source: 'web_form',
          client_request_id: crypto.randomUUID?.(),
        },
      });
      message.success(send ? 'Спасибо! Ответ отправлен' : 'Черновик сохранён');
    } catch (e) {
      message.error(e.message);
    }
  };

  const loading = survey.isPending || current === undefined;

  return (
    <div className="page page--narrow">
      <PageHead title="Самочувствие" sub={survey.data ? `${survey.data.title} · около ${survey.data.estimated_minutes} мин` : ' '} />

      <div className="date-chips" role="group" aria-label="Дата опроса">
        {chips.map((c) => (
          <button
            key={c.date}
            type="button"
            aria-pressed={c.date === date}
            className={`chip${c.date === date ? ' chip--on' : ''}${c.empty && c.date !== date ? ' chip--empty' : ''}`}
            onClick={() => setDate(c.date)}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div className="survey-note">
        Участие добровольное. Ответы помогают увидеть связь нагрузки и усталости — это не оценка работы и не диагноз.
        Руководство видит только оценки по шкалам, без ваших текстов.
      </div>

      {loading ? (
        <Card><Skeleton active paragraph={{ rows: 10 }} /></Card>
      ) : (
        <>
          {submitted && (
            <div className="survey-sent">
              Отправлено {dayjs(current.submitted_at).format('D MMMM в HH:mm')}. Ответ за этот день уже учтён.
            </div>
          )}
          <Card styles={{ body: { padding: '4px 16px 16px' } }}>
            {questions.map((q) => {
              const props = {
                q, value: answers[q.id], disabled: submitted,
                onChange: (v) => setAnswers((a) => ({ ...a, [q.id]: v })),
              };
              if (q.type === 'integer_scale') return <ScaleQuestion key={q.id} {...props} />;
              if (q.type === 'single_choice') return <ChoiceQuestion key={q.id} {...props} />;
              return <TextQuestion key={q.id} {...props} />;
            })}
          </Card>

          {!submitted && (
            <div className="form-actions">
              <Button size="large" disabled={save.isPending} loading={save.isPending && !save.variables?.submit} onClick={() => submit(false)}>
                Сохранить черновик
              </Button>
              <Button size="large" type="primary" disabled={save.isPending} loading={save.isPending && save.variables?.submit} onClick={() => submit(true)}>
                Отправить
              </Button>
            </div>
          )}
        </>
      )}

      <Card title="Мои ответы" style={{ marginTop: 16 }} styles={{ body: { paddingTop: 0 } }}>
        {history.isPending ? <TableSkeleton rows={4} /> : (
          <>
            {!history.data.items.length && <div className="muted" style={{ padding: '12px 0' }}>Пока нет ответов.</div>}
            {history.data.items.map((r) => (
              <div key={r.id} className="history-row">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 500 }}>{dayjs(r.assessment_date).format('dd, D MMMM')}</div>
                  <div className="muted" style={{ fontSize: 13 }}>
                    {r.status === 'submitted' ? `Отправлено в ${dayjs(r.submitted_at).format('HH:mm')}` : 'Черновик'}
                    {r.answers.main_overload_source && ` · ${questions.find((q) => q.id === 'main_overload_source')?.options.find((o) => o.value === r.answers.main_overload_source)?.label?.toLowerCase() ?? ''}`}
                  </div>
                </div>
                <ScoreSquare value={r.answers.fatigue_score} title="Усталость" />
                <ScoreSquare value={r.answers.stress_score} title="Стресс" />
              </div>
            ))}
            <div className="muted" style={{ fontSize: 12, padding: '8px 0 0' }}>Квадраты: усталость · стресс (1–5)</div>
            {history.data.total > HISTORY_PAGE_SIZE && (
              <Pagination
                simple
                size="small"
                current={historyPage}
                pageSize={HISTORY_PAGE_SIZE}
                total={history.data.total}
                onChange={setHistoryPage}
                style={{ marginTop: 12, textAlign: 'center' }}
              />
            )}
          </>
        )}
      </Card>
    </div>
  );
}
