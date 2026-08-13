import { Inter } from 'next/font/google';
import { Toaster } from 'sonner';
import './globals.css';

const inter = Inter({ subsets: ['latin', 'cyrillic'], variable: '--font-inter' });

export const metadata = {
  title: 'HOMEART Data Hub — интеллектуальная база мебельных фабрик',
  description: 'Обработка PDF-прайсов, семантический и визуальный поиск по каталогам премиальных фабрик',
};

export default function RootLayout({ children }) {
  return (
    <html lang="ru" className={inter.variable}>
      <body className={`${inter.className} antialiased bg-zinc-50 text-zinc-900`}>
        {children}
        <Toaster position="top-right" richColors />
      </body>
    </html>
  );
}
