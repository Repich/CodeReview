import { FormEvent, useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { login, register } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

type Mode = 'login' | 'register';

interface Props {
  initialMode?: Mode;
}

function LoginPage({ initialMode = 'login' }: Props) {
  const navigate = useNavigate();
  const { setToken, token } = useAuth();
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [captchaToken, setCaptchaToken] = useState('');
  const [website, setWebsite] = useState('');
  const [isSubmitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const turnstileSiteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY as string | undefined;

  useEffect(() => {
    if (!turnstileSiteKey) return;
    (window as any).turnstileCallback = (token: string) => {
      setCaptchaToken(token);
    };
    const scriptId = 'turnstile-script';
    if (!document.getElementById(scriptId)) {
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js';
      script.async = true;
      script.defer = true;
      document.body.appendChild(script);
    }
    return () => {
      delete (window as any).turnstileCallback;
    };
  }, [turnstileSiteKey]);

  useEffect(() => {
    if (mode === 'register') {
      setCaptchaToken('');
      setWebsite('');
    }
  }, [mode]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      if (mode === 'login') {
        const token = await login({ email, password });
        setToken(token.access_token);
      } else {
        if (turnstileSiteKey && !captchaToken) {
          setError('Подтвердите, что вы не робот.');
          setSubmitting(false);
          return;
        }
        const token = await register({
          email,
          password,
          name,
          captcha_token: captchaToken || undefined,
          website: website || undefined,
        });
        setToken(token.access_token);
      }
      navigate('/runs', { replace: true });
    } catch (err) {
      console.error(err);
      setError('Не удалось выполнить операцию. Проверьте данные и попробуйте снова.');
    } finally {
      setSubmitting(false);
    }
  };

  if (token) {
    return <Navigate to="/runs" replace />;
  }

  return (
    <div className="login-wrapper">
      <div className="login-card">
        <p className="muted" style={{ textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.35rem' }}>
          CodeReview 1C
        </p>
        <h1 style={{ marginBottom: '0.5rem' }}>{mode === 'login' ? 'Добро пожаловать' : 'Создать аккаунт'}</h1>
        <p className="muted" style={{ marginBottom: '1.5rem' }}>
          {mode === 'login'
            ? 'Войдите с учётной записью администратора или тестового пользователя.'
            : 'Заполните форму, чтобы оформить тестовый аккаунт.'}
        </p>

        <div className="tab-switch">
          <button
            type="button"
            className={`btn ${mode === 'login' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setMode('login')}
          >
            Вход
          </button>
          <button
            type="button"
            className={`btn ${mode === 'register' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setMode('register')}
          >
            Регистрация
          </button>
        </div>

        <form onSubmit={handleSubmit} className="form-grid" style={{ marginTop: '1rem', gap: '1rem' }}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete={mode === 'login' ? 'username' : 'email'}
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          {mode === 'register' && (
            <div className="field">
              <label htmlFor="name">Имя</label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </div>
          )}
          {mode === 'register' && (
            <div style={{ display: 'none' }}>
              <label htmlFor="website">Website</label>
              <input
                id="website"
                type="text"
                tabIndex={-1}
                autoComplete="off"
                value={website}
                onChange={(event) => setWebsite(event.target.value)}
              />
            </div>
          )}
          <div className="field">
            <label htmlFor="password">Пароль</label>
            <input
              id="password"
              type="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          {mode === 'register' && turnstileSiteKey && (
            <div className="field">
              <label>Проверка</label>
              <div
                className="cf-turnstile"
                data-sitekey={turnstileSiteKey}
                data-callback="turnstileCallback"
              />
            </div>
          )}
          {error && <div className="alert alert-error">{error}</div>}
          <button type="submit" className="btn btn-primary" disabled={isSubmitting} style={{ width: '100%' }}>
            {isSubmitting ? 'Обрабатываем...' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default LoginPage;
