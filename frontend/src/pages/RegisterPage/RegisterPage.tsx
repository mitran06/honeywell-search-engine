import { Navigate } from 'react-router-dom';
import { HiDocumentText } from 'react-icons/hi';
import { RegisterForm } from '@/components/auth';
import { useAuth } from '@/hooks/useAuth';
import { APP_NAME, ROUTES } from '@/utils/constants';
import styles from './RegisterPage.module.css';

export function RegisterPage() {
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
          <h1 className={styles.title}>Create an account</h1>
          <p className={styles.subtitle}>Get started with {APP_NAME}</p>
        </div>
        <RegisterForm />
      </div>
    </div>
  );
}

export default RegisterPage;
