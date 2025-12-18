import { HiChevronUp, HiChevronDown } from 'react-icons/hi';
import styles from './PageNavigator.module.css';

interface PageNavigatorProps {
  currentHighlight: number;
  totalHighlights: number;
  onPrevious: () => void;
  onNext: () => void;
}

export function PageNavigator({
  currentHighlight,
  totalHighlights,
  onPrevious,
  onNext,
}: PageNavigatorProps) {
  if (totalHighlights === 0) return null;

  return (
    <div className={styles.container}>
      <span className={styles.label}>
        {currentHighlight + 1} of {totalHighlights} matches
      </span>
      <div className={styles.buttons}>
        <button
          type="button"
          className={styles.button}
          onClick={onPrevious}
          disabled={currentHighlight <= 0}
          aria-label="Previous match"
        >
          <HiChevronUp size={20} />
        </button>
        <button
          type="button"
          className={styles.button}
          onClick={onNext}
          disabled={currentHighlight >= totalHighlights - 1}
          aria-label="Next match"
        >
          <HiChevronDown size={20} />
        </button>
      </div>
    </div>
  );
}

export default PageNavigator;
