import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { HiSearch, HiX } from 'react-icons/hi';
import styles from './SearchBar.module.css';

interface SearchBarProps {
  initialQuery?: string;
  placeholder?: string;
  autoFocus?: boolean;
  onSearch?: (query: string) => void;
}

export function SearchBar({
  initialQuery = '',
  placeholder = 'Search your documents...',
  autoFocus = false,
  onSearch,
}: SearchBarProps) {
  const [query, setQuery] = useState(initialQuery);
  const navigate = useNavigate();

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmedQuery = query.trim();
      if (!trimmedQuery) return;

      if (onSearch) {
        onSearch(trimmedQuery);
      } else {
        navigate(`/search?q=${encodeURIComponent(trimmedQuery)}`);
      }
    },
    [query, onSearch, navigate]
  );

  const handleClear = useCallback(() => {
    setQuery('');
  }, []);

  return (
    <form className={styles.searchForm} onSubmit={handleSubmit}>
      <div className={styles.inputWrapper}>
        <HiSearch className={styles.searchIcon} size={20} />
        <input
          type="text"
          className={styles.input}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          autoFocus={autoFocus}
        />
        {query && (
          <button
            type="button"
            className={styles.clearButton}
            onClick={handleClear}
            aria-label="Clear search"
          >
            <HiX size={18} />
          </button>
        )}
      </div>
      <button type="submit" className={styles.submitButton}>
        Search
      </button>
    </form>
  );
}

export default SearchBar;
