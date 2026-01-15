import "./globals.css";
import Providers from "./providers";
import { TransactionsProvider } from "@/context/TransactionsContext";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <TransactionsProvider>{children}</TransactionsProvider>
        </Providers>
      </body>
    </html>
  );
}
