import { useEffect, useRef } from 'react';
import styles from './TextHighlighter.module.css';

interface Highlight {
  text: string;
  startOffset: number;
  endOffset: number;
  boundingBox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

interface TextHighlighterProps {
  highlights: Highlight[];
  containerRef: React.RefObject<HTMLDivElement>;
  scale?: number;
  currentHighlight?: number;
  onHighlightClick?: (index: number) => void;
}

export function TextHighlighter({
  highlights,
  containerRef,
  scale = 1,
  currentHighlight,
  onHighlightClick,
}: TextHighlighterProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !overlayRef.current) return;

    // Position overlay to match container
    const container = containerRef.current;
    const overlay = overlayRef.current;

    const rect = container.getBoundingClientRect();
    overlay.style.width = `${rect.width}px`;
    overlay.style.height = `${rect.height}px`;
  }, [containerRef, scale]);

  if (!highlights.length) return null;

  return (
    <div ref={overlayRef} className={styles.overlay}>
      {highlights.map((highlight, index) => {
        if (!highlight.boundingBox) return null;

        const { x, y, width, height } = highlight.boundingBox;
        const isCurrent = currentHighlight === index;

        return (
          <div
            key={`${highlight.startOffset}-${index}`}
            className={`${styles.highlight} ${isCurrent ? styles.current : ''}`}
            style={{
              left: x * scale,
              top: y * scale,
              width: width * scale,
              height: height * scale,
            }}
            onClick={() => onHighlightClick?.(index)}
            role="button"
            tabIndex={0}
            title={highlight.text}
          />
        );
      })}
    </div>
  );
}

export default TextHighlighter;
