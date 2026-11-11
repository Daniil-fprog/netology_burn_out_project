import { useState } from 'react';
import { Alert, Button, Card, Form, Input, Typography } from 'antd';
import { useSession } from '../session/SessionContext';
import { API_MODE } from '../api/http';

export default function Login() {
  const { login } = useSession();
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(false);

  const submit = async ({ login: name, password }) => {
    setError(null);
    setPending(true);
    try {
      await login(name, password);
    } catch (e) {
      setError(e.status === 401 ? 'Неверный логин или пароль' : e.message);
      setPending(false);
    }
  };

  return (
    <div className="login-wrap">
      <Card className="login-card">
        <Typography.Title level={3} style={{ marginTop: 0 }}>Вход</Typography.Title>
        <Typography.Paragraph type="secondary">Мониторинг нагрузки учителей</Typography.Paragraph>
        {API_MODE === 'mock' && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="Режим заглушек"
            description="Логины: teacher, director, head, group_head, admin. Пароль: demo"
          />
        )}
        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
        <Form layout="vertical" onFinish={submit} requiredMark={false} disabled={pending}>
          <Form.Item name="login" label="Логин" rules={[{ required: true, message: 'Введите логин' }]}>
            <Input autoComplete="username" autoFocus />
          </Form.Item>
          <Form.Item name="password" label="Пароль" rules={[{ required: true, message: 'Введите пароль' }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={pending}>Войти</Button>
        </Form>
      </Card>
    </div>
  );
}
