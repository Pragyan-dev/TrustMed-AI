import './globals.css'

export const metadata = {
  title: 'Synapse AI',
  description: 'Clinical decision support with clinician and patient-facing views.',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  )
}
