// Import the React tool for running something when the page opens
import { useEffect } from 'react'
// Import the icons we use
import { ArrowLeft, TriangleAlert } from 'lucide-react'
// Import our own files
import { BRAND } from '../brand'
import { LEGAL } from '../legal/legalConfig'
import Wordmark from './Logo'

// Show a text, and highlight anything in [square brackets] (these are the blanks that still need filling in)
function Marked({ text }) {
  return text.split(/(\[[^\]]+\])/g).map((part, index) =>
    /^\[[^\]]+\]$/.test(part) ? (
      <mark key={index} className="rounded bg-gold/40 px-1 text-forest-900">
        {part}
      </mark>
    ) : (
      <span key={index}>{part}</span>
    )
  )
}

// A page that shows a legal document: a title, a list of sections, and the text
export default function LegalPage({ title, version, sections, otherTitle, otherHref }) {
  // Put the document's name in the browser tab
  useEffect(() => {
    document.title = `${title} · ${BRAND.name}`
  }, [title])

  return (
    <div className="min-h-screen bg-cream">
      {/* The top bar */}
      <header className="border-b border-forest-100 bg-paper">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-5 py-4">
          <a href="/" aria-label="Home">
            <Wordmark size="sm" />
          </a>
          <a href="/" className="flex items-center gap-1.5 text-sm font-semibold text-forest-700 hover:underline">
            <ArrowLeft size={15} /> Back
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-5 pb-20 pt-8">
        {/* The draft warning (shown until the text has been reviewed and the blanks are filled in) */}
        {LEGAL.draft && (
          <div role="status" className="mb-6 flex items-start gap-3 rounded-2xl bg-amber px-5 py-4 text-sm font-medium text-white">
            <TriangleAlert size={18} className="mt-0.5 shrink-0" />
            <p>DRAFT: this text has not been reviewed by a lawyer yet. The highlighted [brackets] are blanks that still need filling in.</p>
          </div>
        )}

        <h1 className="font-display text-4xl font-extrabold text-forest-900">{title}</h1>
        <p className="mt-2 text-sm text-muted">
          Version {version} · last updated {LEGAL.lastUpdated}
        </p>

        {/* The list of sections */}
        <nav aria-label="Sections" className="mt-6 rounded-2xl bg-paper p-5 shadow-sm">
          <p className="text-sm font-semibold text-forest-900">On this page</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
            {sections.map((section) => (
              <li key={section.id}>
                <a href={`#${section.id}`} className="text-forest-700 hover:underline">
                  {section.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        {/* The text */}
        <div className="mt-8 space-y-8">
          {sections.map((section, number) => (
            <section key={section.id} id={section.id} className="scroll-mt-6">
              <h2 className="font-display text-xl font-bold text-forest-900">
                {number + 1}. {section.title}
              </h2>
              <div className="mt-3 space-y-3 text-[15px] leading-relaxed text-ink/90">
                {section.blocks.map((block, index) =>
                  block.p ? (
                    <p key={index}>
                      <Marked text={block.p} />
                    </p>
                  ) : (
                    <ul key={index} className="list-disc space-y-1.5 pl-5">
                      {block.ul.map((item, itemIndex) => (
                        <li key={itemIndex}>
                          <Marked text={item} />
                        </li>
                      ))}
                    </ul>
                  )
                )}
              </div>
            </section>
          ))}
        </div>

        {/* A link to the other document */}
        <p className="mt-12 border-t border-forest-100 pt-6 text-sm text-muted">
          Also read our{' '}
          <a href={otherHref} className="font-semibold text-forest-700 hover:underline">
            {otherTitle}
          </a>
          .
        </p>
      </main>
    </div>
  )
}