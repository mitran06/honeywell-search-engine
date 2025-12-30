import { HiDocumentText } from 'react-icons/hi';
import type { SearchResult } from '@/types';
import styles from './ResultCard.module.css';

interface ResultCardProps {
  result: SearchResult;
  onClick: (result: SearchResult) => void;
  highlightQuery?: string;
}

export function ResultCard({ result, onClick, highlightQuery }: ResultCardProps) {
  const formatPct = (value?: number) => {
    if (typeof value !== "number" || !isFinite(value)) return "0%"
    return `${Math.round(Math.max(0, Math.min(value, 1)) * 100)}%`
  }


  const getConfidenceClass = (score: number) => {
    if (score >= 80) return styles.high;
    if (score >= 50) return styles.medium;
    return styles.low;
  };

  // Highlight matching terms in snippet
  const renderHighlightedSnippet = () => {
    if (!highlightQuery || !result.snippet) {
      return result.snippet;
    }

    const words = highlightQuery.toLowerCase().split(/\s+/).filter(w => w.length > 2);
    if (words.length === 0) return result.snippet;

    // Build regex for highlighting
    const pattern = new RegExp(`(${words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
    const parts = result.snippet.split(pattern);

    return parts.map((part, i) => {
      const isMatch = words.some(w => part.toLowerCase() === w);
      return isMatch ? (
        <mark key={i} className={styles.highlight}>{part}</mark>
      ) : (
        <span key={i}>{part}</span>
      );
    });
  };

  return (
    <div
      className={styles.card}
      onClick={() => onClick(result)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick(result)}
    >
      <div className={styles.content}>
        <div className={styles.header}>
          <HiDocumentText size={18} className={styles.icon} />
          <span className={styles.documentName}>{result.documentName}</span>
          <span className={styles.pageNumber}>Page {result.pageNumber}</span>
        </div>

        <p className={styles.snippet}>{renderHighlightedSnippet()}</p>

        <div className={styles.scores}>
          {result.hasOie && (
            <span
              className={styles.scoreChip}
              title="Open Information Extraction match"
            >
              OIE ✓
            </span>
          )}
          <span className={styles.scoreChip} title="Semantic similarity">
            Semantic {formatPct(result.scores.semantic)}
          </span>
          <span className={styles.scoreChip} title="Keyword match">
            Lexical {formatPct(result.scores.lexical)}
          </span>
         
        </div>
      </div>

      <div className={styles.confidence}>
        <span className={`${styles.confidenceValue} ${getConfidenceClass(result.confidenceScore)}`}>
          {Math.round(result.confidenceScore)}%
        </span>
        <span className={styles.confidenceLabel}>match</span>
      </div>
    </div>
  );
}

export default ResultCard;
