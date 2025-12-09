import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { HiSearch, HiDocumentText } from 'react-icons/hi';
import { Header } from '@/components/layout/Header';
import { PageContainer } from '@/components/layout/PageContainer';
import { Button, Loader } from '@/components/common';
import { searchApi } from '@/api';
import { CONFIDENCE_THRESHOLDS } from '@/utils/constants';
import type { SearchResult } from '@/types';
import styles from './SearchPage.module.css';

export function SearchPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searchTime, setSearchTime] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setHasSearched(true);

    try {
      const response = await searchApi.search({ query: query.trim(), limit: 20 });
      setResults(response.data.results);
      setSearchTime(response.data.searchTime);
    } catch (error) {
      console.error('Search failed:', error);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  const getScoreClass = (score: number) => {
    if (score >= CONFIDENCE_THRESHOLDS.HIGH) return styles.high;
    if (score >= CONFIDENCE_THRESHOLDS.MEDIUM) return styles.medium;
    return styles.low;
  };

  const handleResultClick = (result: SearchResult) => {
    navigate(`/viewer/${result.documentId}?page=${result.pageNumber}`);
  };

  return (
    <>
      <Header />
      <PageContainer
        title="Search Documents"
        description="Find relevant content across all your PDF documents"
      >
        <div className={styles.searchSection}>
          <form className={styles.searchForm} onSubmit={handleSearch}>
            <div className={styles.searchInputWrapper}>
              <input
                type="text"
                className={styles.searchInput}
                placeholder="Enter a phrase or sentence to search..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                autoFocus
              />
            </div>
            <Button
              type="submit"
              size="lg"
              leftIcon={<HiSearch size={20} />}
              isLoading={isLoading}
              className={styles.searchButton}
            >
              Search
            </Button>
          </form>
        </div>

        {isLoading && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-2xl)' }}>
            <Loader size="lg" text="Searching documents..." />
          </div>
        )}

        {!isLoading && hasSearched && (
          <>
            <div className={styles.resultsHeader}>
              <span className={styles.resultsCount}>
                {results.length} result{results.length !== 1 ? 's' : ''} found
              </span>
              {searchTime !== null && (
                <span className={styles.searchTime}>
                  Search completed in {searchTime.toFixed(3)}s
                </span>
              )}
            </div>

            {results.length > 0 ? (
              <div className={styles.resultsList}>
                {results.map((result, index) => (
                  <div
                    key={`${result.documentId}-${result.pageNumber}-${index}`}
                    className={styles.resultCard}
                    onClick={() => handleResultClick(result)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && handleResultClick(result)}
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
                <p className={styles.emptyDescription}>
                  Try adjusting your search terms or upload more documents
                </p>
              </div>
            )}
          </>
        )}

        {!isLoading && !hasSearched && (
          <div className={styles.emptyState}>
            <HiSearch size={48} className={styles.emptyIcon} />
            <h3 className={styles.emptyTitle}>Start searching</h3>
            <p className={styles.emptyDescription}>
              Enter a phrase or sentence to find relevant content in your documents
            </p>
          </div>
        )}
      </PageContainer>
    </>
  );
}

export default SearchPage;
