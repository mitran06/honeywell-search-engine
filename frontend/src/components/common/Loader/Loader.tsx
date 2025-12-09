import styles from './Loader.module.css';

type LoaderSize = 'sm' | 'md' | 'lg';
type LoaderVariant = 'inline' | 'fullPage' | 'overlay';

interface LoaderProps {
  size?: LoaderSize;
  variant?: LoaderVariant;
  text?: string;
}

export function Loader({ size = 'md', variant = 'inline', text }: LoaderProps) {
  const classNames = [
    styles.loader,
    styles[size],
    variant === 'fullPage' ? styles.fullPage : '',
    variant === 'overlay' ? styles.overlay : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classNames}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div className={styles.spinner} />
        {text && <span className={styles.text}>{text}</span>}
      </div>
    </div>
  );
}

export default Loader;
