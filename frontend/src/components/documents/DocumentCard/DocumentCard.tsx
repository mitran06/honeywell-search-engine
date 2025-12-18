import { HiDocumentText, HiClock, HiTrash } from 'react-icons/hi';
import type { Document } from '@/types';
import { formatFileSize, formatRelativeTime } from '@/utils/formatters';
import styles from './DocumentCard.module.css';

interface DocumentCardProps {
  document: Document;
  onView: (document: Document) => void;
  onDelete?: (document: Document) => void;
}

export function DocumentCard({ document, onView, onDelete }: DocumentCardProps) {
  const getStatusClass = () => {
    switch (document.status) {
      case 'completed':
        return styles.completed;
      case 'processing':
        return styles.processing;
      case 'failed':
      case 'embed_failed':
        return styles.failed;
      default:
        return styles.pending;
    }
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onDelete && window.confirm('Are you sure you want to delete this document?')) {
      onDelete(document);
    }
  };

  return (
    <div
      className={styles.card}
      onClick={() => onView(document)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onView(document)}
    >
      <div className={styles.icon}>
        <HiDocumentText size={32} />
      </div>

      <div className={styles.content}>
        <h3 className={styles.title}>{document.filename}</h3>
        <div className={styles.meta}>
          <span className={styles.size}>{formatFileSize(document.file_size)}</span>
          <span className={styles.separator}>•</span>
          <span className={styles.pages}>{document.page_count ?? '?'} pages</span>
          <span className={styles.separator}>•</span>
          <div className={styles.date}>
            <HiClock size={14} />
            <span>{formatRelativeTime(document.created_at)}</span>
          </div>
        </div>
      </div>

      <div className={styles.actions}>
        <span className={`${styles.status} ${getStatusClass()}`}>
          {document.status}
        </span>
        {onDelete && (
          <button
            type="button"
            className={styles.deleteButton}
            onClick={handleDelete}
            aria-label="Delete document"
          >
            <HiTrash size={18} />
          </button>
        )}
      </div>
    </div>
  );
}

export default DocumentCard;
