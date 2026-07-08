import { h } from 'vue'
import { Icon, _api, addCollection } from '@iconify/vue'
import { NIcon } from 'naive-ui'
import SvgIcon from '@/components/icon/SvgIcon.vue'
import { localIconCollections } from './local-icons.generated'

// Keep menu icons local; blocked Iconify API requests caused blank icons.
_api.setFetch(() => Promise.reject(new Error('Iconify API disabled - using local icons only')))

const localCollections = new Map(localIconCollections.map((collection) => [collection.prefix, collection]))
const loadedCollections = new Set()

function getIconPrefix(icon) {
  const value = String(icon || '')
  if (!value) return ''
  if (value.includes(':')) return value.split(':')[0]
  if (value.startsWith('mdi-')) return 'mdi'
  return ''
}

function loadCollection(prefix) {
  if (!prefix || loadedCollections.has(prefix)) return
  const collection = localCollections.get(prefix)
  if (!collection) return
  addCollection(collection)
  loadedCollections.add(prefix)
}

export function loadLocalIconCollections(icons = []) {
  const prefixes = [...new Set(icons.map(getIconPrefix).filter(Boolean))]
  prefixes.forEach(loadCollection)
}

export function renderIcon(icon, props = { size: 12 }) {
  loadLocalIconCollections([icon])
  return () => h(NIcon, props, { default: () => h(Icon, { icon }) })
}

export function renderCustomIcon(icon, props = { size: 12 }) {
  return () => h(NIcon, props, { default: () => h(SvgIcon, { icon }) })
}
