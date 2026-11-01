// privacyContent.js - the Privacy Policy, as sections of plain text

import { LEGAL } from './legalConfig'

// Shorter names, so the text below is easier to read
const o = LEGAL.operator

export const PRIVACY_SECTIONS = [
  {
    id: 'who',
    title: 'Who we are',
    blocks: [
      {
        p: `EstateLoom is operated by ${o.name}, ${o.address}. You can reach us at ${o.email} or ${o.phone}. Our registration with the Office of the Data Protection Commissioner (ODPC): ${o.odpcNumber}.`,
      },
    ],
  },
  {
    id: 'roles',
    title: 'Two roles: who decides what',
    blocks: [
      { p: 'We have two different roles, and it matters which one applies:' },
      {
        ul: [
          'For the account details of landlords, caretakers and administrators who sign in (names, emails, phone numbers, sign-in records), we decide how the information is used. We are the “data controller”.',
          'For the information a landlord keeps about their tenants and buildings, the landlord decides how it is used. The landlord is the “data controller” and we are their “data processor”. We handle it only to run EstateLoom for them.',
        ],
      },
    ],
  },
  {
    id: 'collect',
    title: 'What information we hold',
    blocks: [
      {
        ul: [
          'Accounts: name, email, phone number, a scrambled version of the password, whether 2-step login is on, and when you last signed in.',
          'What landlords record about tenants: names, phone numbers, ID numbers, emergency contacts, rent, charges, payments (including M-Pesa codes), repair reports, move-in and move-out checklists with photos, documents, and notices.',
          'Vacancy listings: the text and photos a landlord chooses to publish, and the contact phone number they choose to show.',
          'M-Pesa payment prompts: the tenant’s phone number, the amount, and the result and receipt number that Safaricom sends back.',
          'Security records: an activity log of changes made in an account, sign-in attempts, and the internet address they came from.',
          'Error reports: when the service crashes, a technical report is sent to our error-monitoring service. We remove names, phone numbers, passwords and request contents from these reports before they leave our servers.',
        ],
      },
    ],
  },
  {
    id: 'why',
    title: 'Why we use it',
    blocks: [
      {
        ul: [
          'To provide EstateLoom: showing balances, recording payments, sending prompts and notices.',
          'To keep it secure: sign-in checks, locking after wrong passwords, the activity log, and fixing faults.',
          'To run our business with landlords: agreeing plans, recording payments they make to us, and supporting them.',
          'To follow the law.',
        ],
      },
      { p: 'We do not sell personal information, and we do not use it for advertising.' },
    ],
  },
  {
    id: 'share',
    title: 'Who else handles it',
    blocks: [
      { p: 'We use a few companies to run the service. They handle information only on our instructions:' },
      {
        ul: [
          'Render, which hosts the application, the database and the uploaded files, in Frankfurt, Germany.',
          'Sentry, which receives the scrubbed error reports described above [CHECK THAT YOUR SENTRY PROJECT USES THE EU REGION].',
          'Safaricom, when a landlord uses M-Pesa payment prompts. Safaricom handles the payment under its own terms.',
        ],
      },
      {
        p: 'Other services see no customer information: our code is stored on GitHub, and an uptime monitor only checks that our public addresses respond. When a landlord sends a message through WhatsApp from their own phone, WhatsApp handles that message, not us.',
      },
      { p: 'Our staff do not browse landlords’ records. The administrator tools show counts only. A technical administrator with access to the database could in principle see information, so access is limited to [WHO HAS ACCESS], is protected by 2-step login, and is used only to fix problems.' },
      { p: 'We may share information if the law or a court requires it.' },
    ],
  },
  {
    id: 'transfers',
    title: 'Information stored outside Kenya',
    blocks: [
      {
        p: 'Our hosting is in Germany. That means personal information is stored and handled outside Kenya. We use providers that protect information with contracts and technical measures, and we only use providers whose terms allow us to meet our duties under the Data Protection Act, 2019 [CHECK THIS WITH YOUR LAWYER].',
      },
    ],
  },
  {
    id: 'security',
    title: 'How we protect it',
    blocks: [
      {
        ul: [
          'Everything travels over encrypted connections (HTTPS).',
          'Passwords are stored scrambled, never as plain text. Tenants’ ID numbers are scrambled in the database too.',
          'Each landlord sees only their own records. Signed-in sessions end after an hour, and changing a password signs you out everywhere.',
          '2-step login is available for every landlord, and required for administrators.',
          'Too many wrong passwords lock an account for a short time.',
          'Changes are recorded in an activity log that landlords can read.',
          'We keep backups of the database and the uploaded files.',
        ],
      },
      { p: 'No system is perfectly safe. If something goes wrong that affects personal information, we tell the landlord concerned without delay, and in any case within 48 hours of becoming aware, so they can meet their own duties.' },
    ],
  },
  {
    id: 'keep',
    title: 'How long we keep it',
    blocks: [
      {
        ul: [
          'While an account is open, we keep its information.',
          'After an account is closed, we keep the information for 30 days so the landlord can ask for a copy, then we delete it from the live service.',
          'Backups are replaced on their normal schedule, so deleted information can remain in a backup for up to [CHECK HOW LONG YOUR RENDER BACKUPS ARE KEPT, AND WRITE IT HERE].',
          'Records of payments that landlords made to us are kept as long as the law requires for accounting.',
        ],
      },
    ],
  },
  {
    id: 'rights',
    title: 'Your rights',
    blocks: [
      {
        p: 'You may ask to see the personal information held about you, to have mistakes corrected, to have it deleted, to object to how it is used, and to receive a copy. If you are a tenant, please ask your landlord first, because they decide how your information is used. We help landlords answer such requests.',
      },
      { p: `For information we control (see “Two roles” above), write to ${o.email}. If you are unhappy with an answer, you may complain to the Office of the Data Protection Commissioner of Kenya.` },
    ],
  },
  {
    id: 'tenants',
    title: 'If you are a tenant',
    blocks: [
      {
        p: 'Your landlord uses EstateLoom to keep your rent records. Your landlord decides what is recorded about you and why. Usually this is your name, phone number, the unit you rent, what you owe and have paid, repair reports, and sometimes your ID number and move-in photos.',
      },
      {
        ul: [
          'If your landlord gives you portal access, you sign in with your phone number and a password you choose. You see only your own balance, statement, notices and repair reports.',
          'Other tenants cannot see your information, and EstateLoom does not use it for advertising or sell it.',
          'To see, correct or delete your information, ask your landlord first. You may also write to us, and we will pass your request on to them.',
        ],
      },
    ],
  },
  {
    id: 'children',
    title: 'Children',
    blocks: [{ p: 'EstateLoom is for adults. It is not meant for anyone under 18.' }],
  },
  {
    id: 'browser',
    title: 'Cookies and browser storage',
    blocks: [
      {
        p: 'When you sign in, EstateLoom keeps a sign-in token in your browser’s storage so you stay signed in for a short while. We do not use advertising or tracking cookies.',
      },
    ],
  },
  {
    id: 'landlords',
    title: 'For landlords: how we handle your tenants’ information',
    blocks: [
      { p: 'This section sets out our promises as your data processor:' },
      {
        ul: [
          'We process your tenants’ information only to provide EstateLoom to you, and as you instruct through the service.',
          'Anyone at EstateLoom who could see it is bound to keep it confidential.',
          'We keep it secure as described above.',
          'We use the companies listed under “Who else handles it”, and we will tell you before adding a new one that handles your tenants’ information.',
          'We tell you without delay, and within 48 hours, if we learn of a breach that affects it.',
          'We help you answer requests from tenants, and we return or delete your information when your account ends (see “How long we keep it”).',
          'On reasonable request, we will give you what you need to check that we are keeping these promises.',
        ],
      },
    ],
  },
  {
    id: 'changes',
    title: 'Changes to this policy',
    blocks: [
      { p: 'If we change this policy in an important way, we will ask landlords to accept the new version, and tell tenants through their landlord or the notice board.' },
    ],
  },
]