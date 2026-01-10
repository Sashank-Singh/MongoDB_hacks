import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
    title: 'Agent OS - Multi-Agent Workflow Control',
    description: 'A MongoDB-backed control plane for durable, multi-agent workflows',
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en" suppressHydrationWarning>
            <body>{children}</body>
        </html>
    );
}
