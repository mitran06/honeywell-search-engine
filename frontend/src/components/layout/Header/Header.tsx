import { useState, useRef, useEffect } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { HiSearch, HiDocumentText, HiLogout, HiChevronDown } from 'react-icons/hi';
import { useAuth } from '@/hooks/useAuth';
import { APP_NAME, ROUTES } from '@/utils/constants';
import styles from './Header.module.css';

export function Header() {
  const { user, logout, isAuthenticated } = useAuth();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  return (
    <header className={styles.header}>
      <Link to={ROUTES.DASHBOARD} className={styles.logo}>
        <HiDocumentText className={styles.logoIcon} />
        <span>{APP_NAME}</span>
      </Link>

      {isAuthenticated && (
        <>
          <nav className={styles.nav}>
            <NavLink
              to={ROUTES.SEARCH}
              className={({ isActive }) =>
                `${styles.navLink} ${isActive ? styles.active : ''}`
              }
            >
              <HiSearch size={18} />
              Search
            </NavLink>
            <NavLink
              to={ROUTES.DOCUMENTS}
              className={({ isActive }) =>
                `${styles.navLink} ${isActive ? styles.active : ''}`
              }
            >
              <HiDocumentText size={18} />
              Documents
            </NavLink>
          </nav>

          <div className={styles.userSection}>
            <div className={styles.userMenu} ref={dropdownRef}>
              <button
                type="button"
                className={styles.userButton}
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              >
                <div className={styles.avatar}>
                  {user?.name ? getInitials(user.name) : '?'}
                </div>
                <span className={styles.userName}>{user?.name}</span>
                <HiChevronDown size={16} />
              </button>

              {isDropdownOpen && (
                <div className={styles.dropdown}>
                  <button
                    type="button"
                    className={`${styles.dropdownItem} ${styles.danger}`}
                    onClick={() => {
                      logout();
                      setIsDropdownOpen(false);
                    }}
                  >
                    <HiLogout size={18} />
                    Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </header>
  );
}

export default Header;
