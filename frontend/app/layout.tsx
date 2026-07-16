import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Car Insurance Comparison Assistant",
  description: "Upload your policy, compare the market, get a switch-or-stay recommendation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
