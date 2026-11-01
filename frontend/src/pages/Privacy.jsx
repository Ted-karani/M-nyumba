// Import our own files
import LegalPage from '../components/LegalPage'
import { LEGAL } from '../legal/legalConfig'
import { PRIVACY_SECTIONS } from '../legal/privacyContent'

// The public Privacy Policy page
export default function Privacy() {
  return <LegalPage title="Privacy Policy" version={LEGAL.privacyVersion} sections={PRIVACY_SECTIONS} otherTitle="Terms of Service" otherHref="/terms" />
}