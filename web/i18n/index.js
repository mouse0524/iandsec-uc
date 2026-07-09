import { createI18n } from 'vue-i18n'
import { lStorage } from '@/utils'

import { compileI18nMessage } from './messageCompiler.mjs'
import messages from './messages'

const currentLocale = lStorage.get('locale')

const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: currentLocale || 'cn',
  fallbackLocale: 'cn',
  messages: messages,
  messageCompiler: compileI18nMessage,
})

export default i18n
