import './globals.css';
import { Share_Tech_Mono } from 'next/font/google';
import Script from 'next/script'; // Import the Script component

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

        {/* --- GOOGLE ANALYTICS START --- */}
        <Script
          src="https://www.googletagmanager.com/gtag/js?id=G-4VX7V2CDPB"
          strategy="afterInteractive"
        />
        <Script id="google-analytics" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());

            gtag('config', 'G-4VX7V2CDPB');
          `}
        </Script>
        {/* --- GOOGLE ANALYTICS END --- */}
      </body>
    </html>
  );
}
