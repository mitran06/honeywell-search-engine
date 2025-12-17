import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { HiSearch, HiDocumentText, HiArrowLeft } from 'react-icons/hi';
import { Button, Loader } from '@/components/common';
import { searchApi } from '@/api';
import { CONFIDENCE_THRESHOLDS, ROUTES } from '@/utils/constants';
import type { SearchResult } from '@/types';
import styles from './SearchPage.module.css';

export function SearchPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryParam = searchParams.get('q') || '';

  const [results, setResults] = useState<SearchResult[]>([]);
  const [searchTime, setSearchTime] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    const executeSearch = async () => {
      if (!queryParam.trim()) {
        navigate(ROUTES.DASHBOARD);
        return;
      }

      setIsLoading(true);
      setHasSearched(true);

      try {
        const response = await searchApi.search({ query: queryParam.trim(), limit: 20 });
        setResults(response.data.results);
        setSearchTime(response.data.searchTime);
      } catch {
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    };

    executeSearch();
  }, [queryParam, navigate]);

  const getScoreClass = (score: number) => {
    if (score >= CONFIDENCE_THRESHOLDS.HIGH) return styles.high;
    if (score >= CONFIDENCE_THRESHOLDS.MEDIUM) return styles.medium;
    return styles.low;
  };

  const handleResultClick = (result: SearchResult) => {
    navigate(`/viewer/${result.documentId}?page=${result.pageNumber}`);
  };

  return (
    <div style={{ padding: 24 }}>
      <Button
        variant="secondary"
        leftIcon={<HiArrowLeft size={18} />}
        onClick={() => navigate(ROUTES.DASHBOARD)}
        style={{ marginBottom: 16 }}
      >
        Back
      </Button>

      <div className={styles.queryDisplay}>
        <span className={styles.queryLabel}>Results for:</span>
        <span className={styles.queryText}>"{queryParam}"</span>
      </div>

      {isLoading && (
        <div className={styles.loadingContainer}>
          <Loader size="lg" text="Searching..." />
        </div>
      )}

      {!isLoading && hasSearched && (
        <>
          <div className={styles.resultsHeader}>
            <span className={styles.resultsCount}>
              {results.length} result{results.length !== 1 ? 's' : ''}
            </span>
            {searchTime !== null && (
              <span className={styles.searchTime}>in {searchTime.toFixed(3)}s</span>
            )}
          </div>

          {results.length > 0 ? (
            <div className={styles.resultsList}>
              {results.map((result, index) => (
                <div
                  key={`${result.documentId}-${result.pageNumber}-${index}`}
                  className={styles.resultCard}
                  onClick={() => handleResultClick(result)}
                >
                  <div className={styles.resultContent}>
                    <div className={styles.resultHeader}>
                      <HiDocumentText size={18} />
                      <span className={styles.documentName}>{result.documentName}</span>
                      <span className={styles.pageNumber}>Page {result.pageNumber}</span>
                    </div>
                    <p className={styles.snippet}>{result.snippet}</p>
                  </div>
                  <div className={styles.confidenceScore}>
                    <span className={`${styles.scoreValue} ${getScoreClass(result.confidenceScore)}`}>
                      {Math.round(result.confidenceScore)}%
                    </span>
                    <span className={styles.scoreLabel}>match</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className={styles.emptyState}>
              <HiSearch size={48} className={styles.emptyIcon} />
              <h3 className={styles.emptyTitle}>No results found</h3>
              <p className={styles.emptyDescription}>Try different keywords.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default SearchPage;
