import { useState } from 'react';
import { DatePicker, Segmented } from 'antd';
import dayjs from 'dayjs';

const fmt = (d) => d.format('YYYY-MM-DD');

export function presetRange(kind, base = dayjs()) {
  if (kind === 'week') {
    const s = base.startOf('isoWeek');
    return { dateFrom: fmt(s), dateTo: fmt(s.add(6, 'day')) };
  }
  const s = base.startOf('isoWeek').subtract(3, 'week');
  return { dateFrom: fmt(s), dateTo: fmt(base.startOf('isoWeek').add(6, 'day')) };
}

export default function PeriodFilter({ value, onChange }) {
  const { kind, dateFrom, dateTo } = value;
  const [lastCustom, setLastCustom] = useState(kind === 'custom' ? { dateFrom, dateTo } : null);

  const pickKind = (k) => {
    if (k !== 'custom') onChange({ kind: k, ...presetRange(k) });
    else onChange({ kind: k, ...(lastCustom ?? { dateFrom, dateTo }) });
  };

  const pickRange = (r) => {
    if (!r) return;
    const range = { dateFrom: fmt(r[0]), dateTo: fmt(r[1]) };
    setLastCustom(range);
    onChange({ kind: 'custom', ...range });
  };

  return (
    <div className="period-filter">
      <Segmented
        aria-label="Период"
        value={kind}
        options={[
          { value: 'week', label: 'Неделя' },
          { value: 'month', label: '4 недели' },
          { value: 'custom', label: 'Период' },
        ]}
        onChange={pickKind}
      />
      <DatePicker.RangePicker
        aria-label="Даты периода"
        value={[dayjs(dateFrom), dayjs(dateTo)]}
        format="D MMM YYYY"
        allowClear={false}
        className="range-compact"
        onChange={pickRange}
      />
    </div>
  );
}
