import { useMemo } from 'react'

import { parseDescription } from '../lib/description'

/** A job description laid out as headings, paragraphs and lists. */
export function Description({ text }: { text: string }) {
  const blocks = useMemo(() => parseDescription(text), [text])

  return (
    <div className="space-y-3 leading-relaxed">
      {blocks.map((block, index) => {
        if (block.type === 'heading') {
          return (
            // Extra space above separates sections; none for the very first block
            <h3 key={index} className="pt-4 font-display text-base font-semibold first:pt-0">
              {block.text}
            </h3>
          )
        }
        if (block.type === 'list') {
          return (
            <ul key={index} className="list-disc space-y-1.5 pl-5 marker:text-graphite">
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex} className="pl-1">
                  {item}
                </li>
              ))}
            </ul>
          )
        }
        return <p key={index}>{block.text}</p>
      })}
    </div>
  )
}
