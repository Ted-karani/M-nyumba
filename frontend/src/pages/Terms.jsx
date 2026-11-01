// Import our own files
import LegalPage from '../components/LegalPage'
import { LEGAL } from '../legal/legalConfig'
import { TERMS_SECTIONS } from '../legal/termsContent'

// The public Terms of Service page
export default function Terms() {
  return <LegalPage title="Terms of Service" version={LEGAL.termsVersion} sections={TERMS_SECTIONS} otherTitle="Privacy Policy" otherHref="/privacy" />
}