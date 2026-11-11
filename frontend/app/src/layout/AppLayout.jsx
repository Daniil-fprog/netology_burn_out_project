import { useState } from 'react';
import { Layout, Menu, Select, Avatar, Typography, Drawer, Button, Grid, Dropdown } from 'antd';
import { MenuOutlined, ExperimentOutlined, LogoutOutlined } from '@ant-design/icons';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { sections } from '../routes';
import { useSession, ROLE_LABELS } from '../session/SessionContext';
import { API_MODE } from '../api/http';
import { colors } from '../theme';

const { Sider, Header, Content } = Layout;

const DEMO_LOGINS = { teacher: 'teacher', director: 'director', head: 'head', group_head: 'group_head', system_admin: 'admin' };

function Brand() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 20px', fontWeight: 600 }}>
      <div style={{ width: 32, height: 32, borderRadius: 8, background: colors.primary, color: '#fff', display: 'grid', placeItems: 'center', fontSize: 15 }}>Н</div>
      <span style={{ lineHeight: 1.2, fontSize: 15 }}>Нагрузка<br /><span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>учителей</span></span>
    </div>
  );
}

function DevBanner() {
  const { role, login } = useSession();
  const navigate = useNavigate();
  return (
    <div className="dev-banner">
      <ExperimentOutlined />
      <span>Режим заглушек · войти как:</span>
      <Select
        size="small"
        value={role}
        style={{ minWidth: 180 }}
        onChange={async (r) => { await login(DEMO_LOGINS[r], 'demo'); navigate('/'); }}
        options={Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))}
      />
    </div>
  );
}

export default function AppLayout() {
  const { user, role, roleLabel, schools, school, setSchoolId, logout } = useSession();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const screens = Grid.useBreakpoint();
  const isDesktop = screens.lg;
  const [drawerOpen, setDrawerOpen] = useState(false);

  const items = sections
    .filter((s) => s.roles.includes(role))
    .map((s) => ({ key: s.path, icon: s.icon, label: s.label }));
  const selected = items.find((i) => pathname.startsWith(i.key))?.key;

  const menu = (
    <Menu
      mode="inline"
      selectedKeys={selected ? [selected] : []}
      items={items}
      style={{ borderInlineEnd: 0 }}
      onClick={({ key }) => { navigate(key); setDrawerOpen(false); }}
    />
  );

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {isDesktop && (
        <Sider width={248} style={{ borderRight: `1px solid ${colors.border}`, position: 'sticky', top: 0, height: '100vh' }}>
          <Brand />
          {menu}
        </Sider>
      )}
      <Drawer open={!isDesktop && drawerOpen} onClose={() => setDrawerOpen(false)} placement="left" width={280} styles={{ body: { padding: 0 } }} title={null} closable={false}>
        <Brand />
        {menu}
      </Drawer>
      <Layout>
        {API_MODE === 'mock' && <DevBanner />}
        <Header style={{ borderBottom: `1px solid ${colors.border}`, display: 'flex', alignItems: 'center', gap: 12, position: 'sticky', top: 0, zIndex: 10 }}>
          {!isDesktop && <Button type="text" icon={<MenuOutlined />} aria-label="Меню" onClick={() => setDrawerOpen(true)} />}
          {schools.length > 1 ? (
            <Select
              aria-label="Школа"
              value={school?.id}
              onChange={setSchoolId}
              options={schools.map((s) => ({ value: s.id, label: s.name }))}
              style={{ minWidth: 0, maxWidth: 360, flex: '0 1 360px' }}
              popupMatchSelectWidth={false}
            />
          ) : (
            school && <Typography.Text type="secondary" ellipsis style={{ minWidth: 0 }}>{school.name}</Typography.Text>
          )}
          <div style={{ flex: 1 }} />
          <Dropdown
            trigger={['click']}
            menu={{ items: [{ key: 'logout', icon: <LogoutOutlined />, label: 'Выйти', onClick: logout }] }}
          >
            <button type="button" className="user-chip" aria-label="Профиль">
              <span style={{ textAlign: 'right', lineHeight: 1.2, minWidth: 0 }}>
                <Typography.Text strong ellipsis style={{ display: 'block', fontSize: 14 }}>{user.name}</Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 13 }}>{roleLabel}</Typography.Text>
              </span>
              <Avatar style={{ background: colors.soft, color: colors.primary, flex: 'none' }}>{user.name[0]}</Avatar>
            </button>
          </Dropdown>
        </Header>
        <Content>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
