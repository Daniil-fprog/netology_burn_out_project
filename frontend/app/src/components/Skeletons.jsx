// Серые заглушки на время загрузки: повторяют раскладку страницы, чтобы контент
// не «прыгал», когда приходят данные.
import { Card, Col, Row, Skeleton } from 'antd';

export function KpiSkeleton({ count = 4 }) {
  return (
    <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
      {Array.from({ length: count }, (_, i) => (
        <Col key={i} xs={12} md={24 / count}>
          <Card size="small"><Skeleton active title={false} paragraph={{ rows: 2, width: ['40%', '70%'] }} /></Card>
        </Col>
      ))}
    </Row>
  );
}

export function TableSkeleton({ rows = 8 }) {
  return (
    <div aria-busy="true" aria-label="Загрузка">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton-row">
          <Skeleton.Input active size="small" block />
        </div>
      ))}
    </div>
  );
}

export function PageSkeleton({ kpi = true, narrow = false }) {
  return (
    <div className={`page${narrow ? ' page--narrow' : ''}`} aria-busy="true" aria-label="Загрузка страницы">
      <div className="page-head">
        <Skeleton active title={{ width: 260 }} paragraph={{ rows: 1, width: 360 }} />
      </div>
      {kpi && <KpiSkeleton />}
      <Card><TableSkeleton rows={6} /></Card>
    </div>
  );
}

export function FullScreenSkeleton() {
  return (
    <div className="fullscreen-skeleton" aria-busy="true" aria-label="Загрузка">
      <div className="fs-side"><Skeleton active paragraph={{ rows: 8 }} /></div>
      <div className="fs-main"><PageSkeleton /></div>
    </div>
  );
}
