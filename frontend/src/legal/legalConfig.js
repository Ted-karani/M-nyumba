// legalConfig.js - the details that go into the Terms and Privacy Policy

export const LEGAL = {
  // The versions: change these (and the two in backend/legal_models.py) whenever the text changes
  termsVersion: '2026-11-01',
  privacyVersion: '2026-11-01',
  // The date shown at the top of the pages
  lastUpdated: '1 November 2026',
  // While this is true, both pages show a DRAFT banner. Set it to false only after a lawyer has reviewed the text.
  draft: true,
  // Who operates the service (anything in [square brackets] shows up highlighted until you replace it)
  operator: {
    name: '[YOUR FULL NAME, or your registered business name]',
    email: '[YOUR SUPPORT EMAIL]',
    phone: '[YOUR PHONE NUMBER]',
    address: '[YOUR POSTAL OR PHYSICAL ADDRESS], Kenya',
    odpcNumber: '[ODPC REGISTRATION NUMBER, once you have it]',
  },
}