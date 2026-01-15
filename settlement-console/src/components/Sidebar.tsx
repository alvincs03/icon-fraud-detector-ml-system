"use client";

import Image from "next/image";
import styles from "./sidebar.module.css";
import { signIn, signOut, useSession } from "next-auth/react";

export default function Sidebar({ onAddClick }: { onAddClick: () => void }) {
  const { data: session, status } = useSession();
  const authed = status === "authenticated";

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logoWrap}>
        <Image
          src="/logo.png"
          alt="Logo"
          width={300}
          height={300}
          priority
          className={styles.logo}
        />
      </div>

      <button className={styles.addBtn} onClick={onAddClick} type="button">
        Add Transaction
      </button>

      <div className={styles.authBlock}>
        {authed ? (
          <>
            <div className={styles.userLine}>
              Signed in as
              <div className={styles.userName}>
                {session?.user?.name ?? session?.user?.email ?? "User"}
              </div>
            </div>

            <button
              className={styles.authBtn}
              type="button"
              onClick={() => signOut({ callbackUrl: "/" })}
            >
              Sign out
            </button>
          </>
        ) : (
          <button
            className={styles.authBtn}
            type="button"
            onClick={() => signIn("google", { callbackUrl: "/" })}
            disabled={status === "loading"}
          >
            Sign in with Google
          </button>
        )}
      </div>
    </aside>
  );
}
