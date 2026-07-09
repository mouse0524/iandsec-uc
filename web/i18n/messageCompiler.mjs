const PLACEHOLDER_RE = /\{([\w$.-]+)\}/g

export function compileI18nMessage(message) {
  const source = String(message)
  return (ctx) =>
    source.replace(PLACEHOLDER_RE, (_, key) => {
      const value = /^\d+$/.test(key) ? ctx.list(Number(key)) : ctx.named(key)
      return value == null ? '' : String(value)
    })
}
