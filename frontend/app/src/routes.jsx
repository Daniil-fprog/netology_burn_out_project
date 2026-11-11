import {
  DashboardOutlined, TableOutlined, ClockCircleOutlined, SmileOutlined, LineChartOutlined,
  BankOutlined, TagsOutlined, FileExcelOutlined, TeamOutlined,
} from '@ant-design/icons';

const MANAGERS = ['director', 'head', 'group_head'];

export const sections = [
  { key: 'dashboard', path: '/dashboard', label: 'Плановая нагрузка', icon: <DashboardOutlined />, roles: MANAGERS },
  { key: 'plans', path: '/workload/plans', label: 'Управление планом', icon: <TableOutlined />, roles: MANAGERS },
  { key: 'my-workload', path: '/my/workload', label: 'Моя нагрузка', icon: <ClockCircleOutlined />, roles: ['teacher'], narrow: true },
  { key: 'my-survey', path: '/my/surveys/daily', label: 'Самочувствие', icon: <SmileOutlined />, roles: ['teacher'], narrow: true },
  { key: 'analytics', path: '/analytics/teachers', label: 'Аналитика', icon: <LineChartOutlined />, roles: ['teacher', 'head', 'group_head'] },
  { key: 'schools', path: '/schools', label: 'Школы и педагоги', icon: <BankOutlined />, roles: MANAGERS },
  { key: 'work-types', path: '/settings/work-types', label: 'Виды работ', icon: <TagsOutlined />, roles: [...MANAGERS, 'system_admin'] },
  { key: 'reports', path: '/reports', label: 'Отчёты и экспорт', icon: <FileExcelOutlined />, roles: ['teacher', ...MANAGERS] },
  { key: 'users', path: '/settings/users', label: 'Пользователи и права', icon: <TeamOutlined />, roles: ['system_admin'] },
];

export const homePath = {
  teacher: '/my/workload',
  director: '/dashboard',
  head: '/dashboard',
  group_head: '/dashboard',
  system_admin: '/settings/users',
};
