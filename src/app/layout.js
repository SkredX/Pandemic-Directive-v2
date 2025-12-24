import './globals.css';
import { Share_Tech_Mono } from 'next/font/google';

const shareTechMono = Share_Tech_Mono({
  weight: '400',
  subsets: ['latin'],
  variable: '--font-stack',
});

export const metadata = {
  title: 'Pandemic Directive: Zero Hour',
  description: 'ML-Powered Strategic Simulation',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={shareTechMono.className}>
        <div className="screen-effects">
          <div className="scanlines"></div>
          <div className="vignette"></div>
          <div className="noise"></div>
        </div>
        {children}
      </body>
    </html>
  );
}
