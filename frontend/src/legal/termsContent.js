// termsContent.js - the Terms of Service, as sections of plain text

import { LEGAL } from './legalConfig'

// Shorter names, so the text below is easier to read
const o = LEGAL.operator

// Each section has an id (for links), a title, and blocks of text ("p" is a paragraph, "ul" is a list)
export const TERMS_SECTIONS = [
  {
    id: 'who',
    title: 'Who we are and what these terms cover',
    blocks: [
      {
        p: `These terms are an agreement between you (the landlord or business using EstateLoom) and ${o.name}, who operates EstateLoom (“we”, “us”). Our address is ${o.address}. By signing in to EstateLoom you accept these terms.`,
      },
      { p: 'If you use EstateLoom for a business, you confirm that you have the authority to accept these terms for it.' },
      {
        p: 'A caretaker, or a tenant you give access to, uses EstateLoom only through you. You are responsible for what they do with the access you give them.',
      },
    ],
  },
  {
    id: 'service',
    title: 'What EstateLoom does, and what it does not do',
    blocks: [
      { p: 'EstateLoom helps you to:' },
      {
        ul: [
          'record your properties, units, tenants, rent, bills, payments, repairs, documents and notices;',
          'advertise empty units with photos and a link;',
          'give your tenants a portal where they see their own balance and report problems;',
          'send M-Pesa payment prompts to your tenants’ phones, when this has been switched on for your account.',
        ],
      },
      {
        p: 'EstateLoom is a record-keeping tool. It does not give legal, tax or accounting advice. Balances, reports and any tax figures are only as accurate as the information entered, so please check them.',
      },
      { p: 'We do not collect, hold or pass on rent money. Your tenants pay your own M-Pesa Paybill or Till directly.' },
    ],
  },
  {
    id: 'account',
    title: 'Your account',
    blocks: [
      {
        ul: [
          'Give us correct details, and keep them up to date.',
          'Keep your password private. Turn on 2-step login, which we strongly recommend and may require.',
          'Tell us at once if you think someone else has got into your account.',
          'You are responsible for everything done through your account, including by the caretakers and tenants you create accounts for.',
          'We may reset a password or sign you out of your devices, at your request or to keep the service secure.',
        ],
      },
    ],
  },
  {
    id: 'data',
    title: 'Your data and your tenants’ data',
    blocks: [
      { p: 'The information you put into EstateLoom is yours. We do not sell it, and we do not use it for advertising.' },
      {
        p: 'Your tenants’ personal information (such as names, phone numbers, ID numbers, payments and photos) is information you collect for your own purposes. Under the Data Protection Act, 2019 you are the “data controller” and we are your “data processor”. We handle that information only to provide EstateLoom to you, as described in our Privacy Policy.',
      },
      { p: 'As the data controller, you are responsible for:' },
      {
        ul: [
          'having a lawful reason to hold your tenants’ information, and only collecting what you really need;',
          'telling your tenants how their information is used (our Privacy Policy has a section for tenants that you may point them to);',
          'keeping the information accurate, and registering with the Office of the Data Protection Commissioner if the law requires it;',
          'not entering information you have no right to enter.',
        ],
      },
    ],
  },
  {
    id: 'plans',
    title: 'Plans, payment and ending your account',
    blocks: [
      {
        ul: [
          'A pilot is a free trial for the period we agree with you. A paid plan has a price and a period that we agree with you in writing (a message counts). Current prices are the ones we agree with you.',
          'Every plan has an access end date. After that date, your account has 7 days of grace. Then it becomes read-only: you can look at and download your records, but you cannot add or change anything. Paying brings it back.',
          'We may suspend an account that breaks these terms or puts others at risk, and we will tell you why where we can.',
          'You can close your account at any time by telling us. After that we keep your data for 30 days so you can ask for a copy, and then we delete it from the live service. Backups are cleared on their normal schedule (see the Privacy Policy).',
          'Refunds: [DECIDE YOUR REFUND POLICY, for example: unused full months are refunded on request].',
        ],
      },
    ],
  },
  {
    id: 'use',
    title: 'Using EstateLoom properly',
    blocks: [
      { p: 'Please do not:' },
      {
        ul: [
          'use EstateLoom for anything unlawful, or to harass or discriminate against tenants;',
          'upload content you have no right to, or that is unlawful;',
          'publish a vacancy listing that is untrue, or that uses photos you have no right to use;',
          'try to reach other people’s data, test our security, or overload the service;',
          'share your login with people who are not part of your business.',
        ],
      },
      { p: 'We may remove content or listings that break these rules.' },
    ],
  },
  {
    id: 'mpesa',
    title: 'M-Pesa payment prompts',
    blocks: [
      {
        p: 'When payment prompts are on for your account, a prompt appears on a tenant’s phone for an amount you or the tenant choose. The money goes from the tenant’s M-Pesa straight to your own Paybill or Till. Safaricom controls the payment, and Safaricom’s own terms and charges apply.',
      },
      {
        p: 'Payments can fail, arrive late, or be reversed. EstateLoom records a payment only after Safaricom confirms it, but you must compare your records with your M-Pesa statement. We are not responsible for failed or reversed payments, or for outages at Safaricom. You must have the right to use any Paybill, Till or access keys you ask us to connect.',
      },
    ],
  },
  {
    id: 'availability',
    title: 'Availability and backups',
    blocks: [
      {
        p: 'We work hard to keep EstateLoom available and your information safe, and we keep backups. But we cannot promise that it will always be available or free of errors. Please download your own copies (the reports and Excel files) regularly.',
      },
    ],
  },
  {
    id: 'liability',
    title: 'Our responsibility to you',
    blocks: [
      {
        p: 'As far as the law allows, we are not responsible for indirect or consequential losses, such as lost rent, lost profit or lost opportunities. As far as the law allows, our total responsibility for any claim is limited to the fees you paid us in the 3 months before the claim [CHECK THIS LIMIT WITH YOUR LAWYER]. Nothing in these terms limits responsibility that the law does not allow us to limit.',
      },
    ],
  },
  {
    id: 'changes',
    title: 'Changes',
    blocks: [
      {
        p: 'We may improve or change EstateLoom, and we may update these terms. When a change is important, we will ask you to accept the new version the next time you sign in. If you do not agree, you may close your account.',
      },
    ],
  },
  {
    id: 'law',
    title: 'The law, and disagreements',
    blocks: [
      {
        p: 'These terms follow the laws of Kenya. If we disagree, let us first try to sort it out by talking. If that fails, the courts of Kenya can decide [CHECK THIS WITH YOUR LAWYER].',
      },
    ],
  },
  {
    id: 'contact',
    title: 'Contact us',
    blocks: [{ p: `Write to ${o.email} or call ${o.phone}.` }],
  },
]