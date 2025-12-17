import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { HiLogout, HiChevronDown } from "react-icons/hi";

import { useAuth } from "@/hooks/useAuth";
import { APP_NAME, ROUTES } from "@/utils/constants";
import { setTheme } from "@/utils/theme";

import styles from "./Header.module.css";

export function Header() {
  const { user, logout, isAuthenticated } = useAuth();

  const [isAccountOpen, setIsAccountOpen] = useState(false);
  const [isThemeOpen, setIsThemeOpen] = useState(false);

  const accountRef = useRef<HTMLDivElement>(null);
  const themeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        accountRef.current &&
        !accountRef.current.contains(e.target as Node)
      ) {
        setIsAccountOpen(false);
      }

      if (
        themeRef.current &&
        !themeRef.current.contains(e.target as Node)
      ) {
        setIsThemeOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const getInitials = (name: string) =>
    name
      .split(" ")
      .map(p => p[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);

  const currentTheme =
    (localStorage.getItem("theme") as string) || "dark";

  return (
    <header className={styles.header}>
      <Link to={ROUTES.DASHBOARD} className={styles.logo}>
        {APP_NAME}
      </Link>

      {isAuthenticated && (
        <div className={styles.userSection}>
          {/* THEME DROPDOWN */}
          <div className={styles.userMenu} ref={themeRef}>
            <button
              className={styles.userButton}
              onClick={() => setIsThemeOpen(v => !v)}
            >
              <span>Theme</span>
              <HiChevronDown size={16} />
            </button>

            {isThemeOpen && (
              <div className={styles.dropdown}>
                {[
                  { key: "light", label: "Light" },
                  { key: "dark", label: "Dark" },
                  { key: "blue-pink", label: "Aurora" },
                  { key: "custom", label: "Obsidian" },
                ].map(t => (
                  <button
                    key={t.key}
                    onClick={() => {
                      setTheme(t.key as any);
                      setIsThemeOpen(false);
                    }}
                    className={`${styles.dropdownItem} ${
                      currentTheme === t.key ? styles.active : ""
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* ACCOUNT DROPDOWN */}
          <div className={styles.userMenu} ref={accountRef}>
            <button
              className={styles.userButton}
              onClick={() => setIsAccountOpen(v => !v)}
            >
              <div className={styles.avatar}>
                {user?.name ? getInitials(user.name) : "?"}
              </div>
              <span className={styles.userName}>{user?.name}</span>
              <HiChevronDown size={16} />
            </button>

            {isAccountOpen && (
              <div className={styles.dropdown}>
                <button
                  className={`${styles.dropdownItem} ${styles.danger}`}
                  onClick={() => {
                    logout();
                    setIsAccountOpen(false);
                  }}
                >
                  <HiLogout size={18} />
                  <span>Logout</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

export default Header;
