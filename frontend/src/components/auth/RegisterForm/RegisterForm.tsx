import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { HiMail, HiLockClosed, HiEye, HiEyeOff, HiUser } from 'react-icons/hi';
import { Button, Input } from '@/components/common';
import { useAuth } from '@/hooks/useAuth';
import { validateRegisterForm, type ValidationError } from '@/utils/validators';
import { ROUTES } from '@/utils/constants';
import styles from './RegisterForm.module.css';

export function RegisterForm() {
  const navigate = useNavigate();
  const { register } = useAuth();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<ValidationError[]>([]);
  const [apiError, setApiError] = useState('');
  const [success, setSuccess] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const getFieldError = (field: string) => {
    return errors.find((e) => e.field === field)?.message;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setApiError('');
    setSuccess('');

    const validationErrors = validateRegisterForm(name, email, password, confirmPassword);
    if (validationErrors.length > 0) {
      setErrors(validationErrors);
      return;
    }

    setErrors([]);
    setIsLoading(true);

    try {
      await register({ name, email, password });
      setSuccess('Account created successfully! Redirecting to login...');
      setTimeout(() => {
        navigate(ROUTES.LOGIN);
      }, 2000);
    } catch (err) {
      const error = err as { response?: { data?: { message?: string } } };
      setApiError(error.response?.data?.message || 'Registration failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      {apiError && <div className={styles.error}>{apiError}</div>}
      {success && <div className={styles.success}>{success}</div>}

      <Input
        label="Name"
        type="text"
        name="name"
        placeholder="Enter your name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        error={getFieldError('name')}
        leftIcon={<HiUser size={18} />}
        required
        autoComplete="name"
      />

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
        placeholder="Create a password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={getFieldError('password')}
        helperText="Must be at least 8 characters"
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
        autoComplete="new-password"
      />

      <Input
        label="Confirm Password"
        type={showPassword ? 'text' : 'password'}
        name="confirmPassword"
        placeholder="Confirm your password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        error={getFieldError('confirmPassword')}
        leftIcon={<HiLockClosed size={18} />}
        required
        autoComplete="new-password"
      />

      <Button
        type="submit"
        fullWidth
        isLoading={isLoading}
        className={styles.submitButton}
      >
        Create Account
      </Button>

      <div className={styles.footer}>
        Already have an account? <Link to={ROUTES.LOGIN}>Sign in</Link>
      </div>
    </form>
  );
}

export default RegisterForm;
