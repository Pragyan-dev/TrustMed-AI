'use client'

import dynamic from 'next/dynamic'

const ClinicianDashboard = dynamic(
  () => import('../../src/views/ClinicianDashboard'),
  {
    ssr: false,
    loading: () => <div className="tm-next-loading">Loading clinician dashboard...</div>,
  }
)

export default function ClinicianPage() {
  return <ClinicianDashboard />
}
