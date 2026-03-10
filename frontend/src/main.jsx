import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import './layouts.css'

import RoleSelector from './pages/RoleSelector'
import ClinicianDashboard from './pages/ClinicianDashboard'
import PatientLayout from './layouts/PatientLayout'
import PatientPortal from './pages/PatientPortal'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Landing — role selector */}
        <Route path="/" element={<RoleSelector />} />

        {/* Clinician — full dashboard (self-contained layout) */}
        <Route path="/clinician" element={<ClinicianDashboard />} />

        {/* Patient portal — light navbar layout */}
        <Route path="/patient" element={<PatientLayout />}>
          <Route index element={<PatientPortal />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
