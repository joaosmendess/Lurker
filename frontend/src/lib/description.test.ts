import { describe, expect, it } from 'vitest'

import { parseDescription } from './description'

describe('parseDescription', () => {
  it('builds headings, lists and paragraphs from a tidied Gupy description', () => {
    const text = [
      'Na Acme, acreditamos em pessoas.',
      'Responsabilidades e atribuições',
      '- Desenvolver APIs.',
      '- Revisar código.',
      'Informações adicionais',
      'Trabalho remoto.',
    ].join('\n')

    expect(parseDescription(text)).toEqual([
      { type: 'paragraph', text: 'Na Acme, acreditamos em pessoas.' },
      { type: 'heading', text: 'Responsabilidades e atribuições' },
      { type: 'list', items: ['Desenvolver APIs.', 'Revisar código.'] },
      { type: 'heading', text: 'Informações adicionais' },
      { type: 'paragraph', text: 'Trabalho remoto.' },
    ])
  })

  it('treats a short line ending in ":" as a heading and drops the colon', () => {
    expect(parseDescription('Nossa Cultura:\nSomos diretos.')).toEqual([
      { type: 'heading', text: 'Nossa Cultura' },
      { type: 'paragraph', text: 'Somos diretos.' },
    ])
  })

  it('treats a short line right before a list as a heading', () => {
    expect(parseDescription('What You’ll Do\n- Ship features')[0]).toEqual({
      type: 'heading',
      text: 'What You’ll Do',
    })
  })

  it('treats short ALL CAPS lines as headings', () => {
    expect(parseDescription('REQUISITOS\nExperiência com C#.')[0]).toEqual({
      type: 'heading',
      text: 'REQUISITOS',
    })
  })

  it('treats a short title-like line before a long paragraph as a heading', () => {
    const paragraph =
      'Our technology team operates under a remote-first model, so you can live anywhere in Brazil.'
    expect(parseDescription(`Location & Remote Work\n${paragraph}`)[0]).toEqual({
      type: 'heading',
      text: 'Location & Remote Work',
    })
  })

  it('does not treat a sentence broken mid-way (lowercase start) as a heading', () => {
    const paragraph =
      'adequadas para o trabalho, com equipamentos e ferramentas para que você possa trabalhar bem.'
    expect(parseDescription(`estrutura da Empresa em condições\n${paragraph}`)[0].type).toBe(
      'paragraph',
    )
  })

  it('keeps ambiguous short lines as paragraphs', () => {
    // Consecutive short lines (e.g. a culture list without bullets) are not headings
    const blocks = parseDescription('💚 O cliente é a razão\n⚡ Cabeça de dono\nFim.')
    expect(blocks.every((block) => block.type === 'paragraph')).toBe(true)
  })

  it('never makes the last line or a sentence a heading', () => {
    expect(parseDescription('Uma frase.\nÚltima linha')).toEqual([
      { type: 'paragraph', text: 'Uma frase.' },
      { type: 'paragraph', text: 'Última linha' },
    ])
  })
})
