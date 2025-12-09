import { useNavigate } from 'react-router-dom';
import { HiDocumentText, HiSearch, HiUpload, HiCollection } from 'react-icons/hi';
import { Header } from '@/components/layout/Header';
import { PageContainer } from '@/components/layout/PageContainer';
import { useAuth } from '@/hooks/useAuth';
import { ROUTES } from '@/utils/constants';
import styles from './DashboardPage.module.css';

export function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const stats = [
    { icon: HiDocumentText, label: 'Total Documents', value: '—' },
    { icon: HiSearch, label: 'Searches Today', value: '—' },
    { icon: HiCollection, label: 'Pages Indexed', value: '—' },
  ];

  const quickActions = [
    {
      icon: HiSearch,
      title: 'Search Documents',
      description: 'Find relevant content across all your PDFs',
      onClick: () => navigate(ROUTES.SEARCH),
    },
    {
      icon: HiUpload,
      title: 'Upload PDF',
      description: 'Add new documents to your library',
      onClick: () => navigate(ROUTES.DOCUMENTS),
    },
    {
      icon: HiDocumentText,
      title: 'View Documents',
      description: 'Browse and manage your uploaded files',
      onClick: () => navigate(ROUTES.DOCUMENTS),
    },
  ];

  return (
    <>
      <Header />
      <PageContainer
        title={`Welcome back, ${user?.name?.split(' ')[0] || 'User'}!`}
        description="Here's an overview of your document library"
      >
        <div className={styles.stats}>
          {stats.map((stat) => (
            <div key={stat.label} className={styles.statCard}>
              <div className={styles.statIcon}>
                <stat.icon size={24} />
              </div>
              <div className={styles.statContent}>
                <p className={styles.statValue}>{stat.value}</p>
                <p className={styles.statLabel}>{stat.label}</p>
              </div>
            </div>
          ))}
        </div>

        <h2 style={{ marginBottom: 'var(--spacing-md)', fontSize: 'var(--font-size-lg)' }}>
          Quick Actions
        </h2>
        <div className={styles.quickActions}>
          {quickActions.map((action) => (
            <div
              key={action.title}
              className={styles.actionCard}
              onClick={action.onClick}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && action.onClick()}
            >
              <div className={styles.actionIcon}>
                <action.icon size={24} />
              </div>
              <div className={styles.actionContent}>
                <h3 className={styles.actionTitle}>{action.title}</h3>
                <p className={styles.actionDescription}>{action.description}</p>
              </div>
            </div>
          ))}
        </div>
      </PageContainer>
    </>
  );
}

export default DashboardPage;
