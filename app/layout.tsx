import type { Metadata } from "next";
import { AppProvider } from "@/lib/context/app-context";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sagefold — Private Knowledge Workspace",
  description: "Ask questions across your documents in a private knowledge workspace.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className="font-sans antialiased"
      >
        <AppProvider>
          {children}
          <Toaster richColors closeButton />
        </AppProvider>
      </body>
    </html>
  );
}

