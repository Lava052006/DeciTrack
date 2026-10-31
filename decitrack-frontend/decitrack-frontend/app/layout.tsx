import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DeciTrack — Clear work, better decisions",
  description: "A calmer view of your tasks, meetings, and team decisions.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
