import { Navigate } from 'react-router-dom';
import { HiDocumentText } from 'react-icons/hi';
import { LoginForm } from '@/components/auth';
import { useAuth } from '@/hooks/useAuth';
import { APP_NAME, ROUTES } from '@/utils/constants';
import styles from './LoginPage.module.css';

export function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();

  if (!isLoading && isAuthenticated) {
    return <Navigate to={ROUTES.DASHBOARD} replace />;
  }

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.logo}>
            <HiDocumentText size={32} />
            <span>{APP_NAME}</span>
          </div>
          <h1 className={styles.title}>Welcome back</h1>
          <p className={styles.subtitle}>Sign in to your account to continue</p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}

export default LoginPage;
