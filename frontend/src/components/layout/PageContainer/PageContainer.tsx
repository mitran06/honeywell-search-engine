import { type ReactNode } from 'react';
import styles from './PageContainer.module.css';

interface PageContainerProps {
  children: ReactNode;
  title?: string;
  description?: string;
  action?: ReactNode;
  fullWidth?: boolean;
  noPadding?: boolean;
  centered?: boolean;
}

export function PageContainer({
  children,
  title,
  description,
  action,
  fullWidth = false,
  noPadding = false,
  centered = false,
}: PageContainerProps) {
  const classNames = [
    styles.container,
    fullWidth ? styles.fullWidth : '',
    noPadding ? styles.noPadding : '',
    centered ? styles.centered : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classNames}>
      <div className={styles.content}>
        {(title || action) && (
          <div className={styles.pageHeader}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                {title && <h1 className={styles.pageTitle}>{title}</h1>}
                {description && <p className={styles.pageDescription}>{description}</p>}
              </div>
              {action && <div>{action}</div>}
            </div>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}

export default PageContainer;
