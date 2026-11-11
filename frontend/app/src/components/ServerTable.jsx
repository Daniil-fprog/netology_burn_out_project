// Таблица с серверной пагинацией: принимает ответ backend { page, page_size, total, items }.
// Первая загрузка — серые строки; смена страницы — прошлые данные остаются на месте.
import { Table } from 'antd';
import { TableSkeleton } from './Skeletons';

export const PAGE_SIZES = [20, 50, 100];

export default function ServerTable({ query, page, pageSize, onPageChange, ...rest }) {
  const { data, isPending, isFetching, isPlaceholderData } = query;
  if (isPending) return <TableSkeleton rows={Math.min(pageSize, 10)} />;
  return (
    <Table
      rowKey="id"
      dataSource={data?.items ?? []}
      loading={isFetching && isPlaceholderData ? { delay: 200 } : false}
      pagination={{
        current: page,
        pageSize,
        total: data?.total ?? 0,
        pageSizeOptions: PAGE_SIZES,
        showSizeChanger: (data?.total ?? 0) > PAGE_SIZES[0],
        showTotal: (total, [from, to]) => `${from}–${to} из ${total}`,
        onChange: (p, size) => onPageChange(size !== pageSize ? 1 : p, size),
        hideOnSinglePage: true,
      }}
      scroll={{ x: 720 }}
      {...rest}
    />
  );
}
