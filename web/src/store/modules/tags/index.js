import { defineStore } from 'pinia'
import { activeTag, tags, WITHOUT_TAG_PATHS } from './helpers'
import { router } from '@/router'
import { lStorage } from '@/utils'
import { useUserStore } from '@/store'

function collectPaths(routes = [], bucket = []) {
  routes.forEach((item) => {
    if (item?.path) bucket.push(item.path)
    if (Array.isArray(item?.children) && item.children.length) collectPaths(item.children, bucket)
  })
  return bucket
}

function getRoleDefaultPath() {
  const userStore = useUserStore()
  if (userStore.isSuperUser) return '/workbench'
  return '/ticket/issues'
}

export const useTagsStore = defineStore('tag', {
  state() {
    return {
      tags: tags || [],
      activeTag: activeTag || '',
    }
  },
  getters: {
    activeIndex() {
      return this.tags.findIndex((item) => item.path === this.activeTag)
    },
  },
  actions: {
    setActiveTag(path) {
      this.activeTag = path
      lStorage.set('activeTag', path)
    },
    setTags(tags) {
      this.tags = tags
      lStorage.set('tags', tags)
    },
    addTag(tag = {}) {
      this.setActiveTag(tag.path)
      if (WITHOUT_TAG_PATHS.includes(tag.path) || this.tags.some((item) => item.path === tag.path))
        return
      this.setTags([...this.tags, tag])
    },
    removeTag(path) {
      if (path === this.activeTag) {
        if (this.tags.length <= 1) {
          router.push(getRoleDefaultPath())
        } else if (this.activeIndex > 0) {
          router.push(this.tags[this.activeIndex - 1].path)
        } else {
          router.push(this.tags[this.activeIndex + 1].path)
        }
      }
      this.setTags(this.tags.filter((tag) => tag.path !== path))
    },
    sanitizeByMenus(menus = []) {
      const allow = new Set(collectPaths(menus || []).filter((path) => !WITHOUT_TAG_PATHS.includes(path)))
      const filtered = (this.tags || []).filter((tag) => allow.has(tag.path))
      this.setTags(filtered)
      if (!filtered.find((item) => item.path === this.activeTag)) {
        const nextPath = filtered[filtered.length - 1]?.path || getRoleDefaultPath()
        this.setActiveTag(nextPath)
      }
    },
    removeOther(curPath = this.activeTag) {
      this.setTags(this.tags.filter((tag) => tag.path === curPath))
      if (curPath !== this.activeTag) {
        router.push(this.tags[this.tags.length - 1].path)
      }
    },
    removeLeft(curPath) {
      const curIndex = this.tags.findIndex((item) => item.path === curPath)
      const filterTags = this.tags.filter((item, index) => index >= curIndex)
      this.setTags(filterTags)
      if (!filterTags.find((item) => item.path === this.activeTag)) {
        router.push(filterTags[filterTags.length - 1].path)
      }
    },
    removeRight(curPath) {
      const curIndex = this.tags.findIndex((item) => item.path === curPath)
      const filterTags = this.tags.filter((item, index) => index <= curIndex)
      this.setTags(filterTags)
      if (!filterTags.find((item) => item.path === this.activeTag)) {
        router.push(filterTags[filterTags.length - 1].path)
      }
    },
    resetTags() {
      this.setTags([])
      this.setActiveTag('')
    },
  },
})
