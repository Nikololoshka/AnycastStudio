import { useNavigate } from 'react-router';
import { useLogoutMutation } from '../../api';

export function useSignOut() {
  const navigate = useNavigate();
  const [logout] = useLogoutMutation();

  return async () => {
    await logout()
      .unwrap()
      .catch(() => undefined);
    void navigate('/login', { replace: true });
  };
}
