import { HiSearch } from 'react-icons/hi';
import type { SearchResult } from '@/types';
import { ResultCard } from '../ResultCard';
import styles from './SearchResults.module.css';

interface SearchResultsProps {
  results: SearchResult[];
  query: string;
  searchTime?: number;
  onResultClick: (result: SearchResult) => void;
}

export function SearchResults({
  results,
  query,
  searchTime,
  onResultClick,
}: SearchResultsProps) {
  if (results.length === 0) {
    return (
      <div className={styles.empty}>
        <HiSearch size={48} className={styles.emptyIcon} />
        <h3 className={styles.emptyTitle}>No results found</h3>
        <p className={styles.emptyDescription}>
          Try adjusting your search terms or upload more documents
        </p>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.count}>
          {results.length} result{results.length !== 1 ? 's' : ''} found
        </span>
        {searchTime !== undefined && (
          <span className={styles.time}>in {searchTime.toFixed(3)}s</span>
        )}
      </div>

      <div className={styles.list}>
        {results.map((result, index) => (
          <ResultCard
            key={`${result.documentId}-${result.pageNumber}-${index}`}
            result={result}
            onClick={onResultClick}
            highlightQuery={query}
          />
        ))}
      </div>
    </div>
  );
}

export default SearchResults;
