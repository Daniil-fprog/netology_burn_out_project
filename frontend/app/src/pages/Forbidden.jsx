import { Result, Button } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../session/SessionContext';
import { homePath } from '../routes';

export default function Forbidden({ message }) {
  const navigate = useNavigate();
  const { role } = useSession();
  return (
    <Result
      status="403"
      title="Нет доступа"
      subTitle={message ?? 'Этот раздел недоступен для вашей роли.'}
      extra={<Button type="primary" onClick={() => navigate(homePath[role] ?? '/')}>На главную</Button>}
    />
  );
}
