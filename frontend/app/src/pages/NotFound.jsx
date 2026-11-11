import { Result, Button } from 'antd';
import { useNavigate } from 'react-router-dom';

export default function NotFound() {
  const navigate = useNavigate();
  return <Result status="404" title="Страница не найдена" extra={<Button onClick={() => navigate('/')}>На главную</Button>} />;
}
