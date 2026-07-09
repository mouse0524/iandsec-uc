import assert from 'node:assert/strict'
import { compileI18nMessage } from './messageCompiler.mjs'

assert.equal(
  compileI18nMessage('hello, {username}')({
    named: (key) => ({ username: 'fenghao' })[key],
    list: () => undefined,
  }),
  'hello, fenghao'
)

assert.equal(
  compileI18nMessage('第 {0} 项')({
    named: () => undefined,
    list: (index) => ['一'][index],
  }),
  '第 一 项'
)
