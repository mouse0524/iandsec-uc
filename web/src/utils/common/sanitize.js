export function sanitizeHtml(input = '') {
  const html = String(input || '')
  if (!html) return ''

  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  const allowedTags = new Set(['P', 'BR', 'STRONG', 'EM', 'UL', 'OL', 'LI', 'A', 'IMG', 'BLOCKQUOTE', 'CODE', 'PRE', 'SPAN', 'H1', 'H2', 'H3', 'H4', 'TABLE', 'THEAD', 'TBODY', 'TR', 'TH', 'TD'])

  const walk = (node) => {
    const children = Array.from(node.children || [])
    for (const child of children) {
      const tag = child.tagName?.toUpperCase()
      if (!allowedTags.has(tag)) {
        child.replaceWith(...Array.from(child.childNodes || []))
        continue
      }

      const attrs = Array.from(child.attributes || [])
      for (const attr of attrs) {
        const name = attr.name.toLowerCase()
        const value = String(attr.value || '').trim()
        if (name.startsWith('on')) {
          child.removeAttribute(attr.name)
          continue
        }
        if (name === 'href') {
          if (!/^https?:\/\//i.test(value) && !value.startsWith('/') && !value.startsWith('#')) {
            child.removeAttribute(attr.name)
          }
          continue
        }
        if (name === 'src') {
          const ok = /^data:image\//i.test(value) || /^blob:/i.test(value) || /^https?:\/\//i.test(value) || value.startsWith('/')
          if (!ok) child.removeAttribute(attr.name)
          continue
        }
        if (!['alt', 'title', 'target', 'rel', 'class', 'loading', 'decoding', 'data-secure-asset'].includes(name)) {
          child.removeAttribute(attr.name)
        }
      }

      if (tag === 'A') {
        child.setAttribute('rel', 'noopener noreferrer')
        if (child.getAttribute('target') === '_blank') child.setAttribute('target', '_blank')
      }

      walk(child)
    }
  }

  walk(doc.body)
  return doc.body.innerHTML
}

export function htmlToPlainText(input = '') {
  return String(input || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function isImageName(name = '') {
  return /\.(png|jpe?g|gif)$/i.test(String(name || ''))
}
