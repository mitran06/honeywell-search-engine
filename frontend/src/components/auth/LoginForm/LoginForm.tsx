import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { HiMail, HiLockClosed, HiEye, HiEyeOff } from 'react-icons/hi';
import { Button, Input } from '@/components/common';
import { useAuth } from '@/hooks/useAuth';
import { validateLoginForm, type ValidationError } from '@/utils/validators';
import { ROUTES } from '@/utils/constants';
import styles from './LoginForm.module.css';

export function LoginForm() {
  const navigate = useNavigate();
  const { login } = useAuth();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<ValidationError[]>([]);
  const [apiError, setApiError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const getFieldError = (field: string) => {
    return errors.find((e) => e.field === field)?.message;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setApiError('');
    
    const validationErrors = validateLoginForm(email, password);
    if (validationErrors.length > 0) {
      setErrors(validationErrors);
      return;
    }
    
    setErrors([]);
    setIsLoading(true);

    try {
      await login({ email, password });
      navigate(ROUTES.DASHBOARD);
    } catch (err) {
      const error = err as { response?: { data?: { message?: string } } };
      setApiError(error.response?.data?.message || 'Invalid email or password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      {apiError && <div className={styles.error}>{apiError}</div>}
      
      <Input
        label="Email"
        type="email"
        name="email"
        placeholder="Enter your email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={getFieldError('email')}
        leftIcon={<HiMail size={18} />}
        required
        autoComplete="email"
      />

      <Input
        label="Password"
        type={showPassword ? 'text' : 'password'}
        name="password"
        placeholder="Enter your password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={getFieldError('password')}
        leftIcon={<HiLockClosed size={18} />}
        rightIcon={
          <button
            type="button"
            className={styles.passwordToggle}
            onClick={() => setShowPassword(!showPassword)}
            tabIndex={-1}
          >
            {showPassword ? <HiEyeOff size={18} /> : <HiEye size={18} />}
          </button>
        }
        required
        autoComplete="current-password"
      />

      <Button
        type="submit"
        fullWidth
        isLoading={isLoading}
        className={styles.submitButton}
      >
        Sign In
      </Button>

      <div className={styles.footer}>
        Don't have an account? <Link to={ROUTES.REGISTER}>Sign up</Link>
      </div>
    </form>
  );
}

export default LoginForm;
