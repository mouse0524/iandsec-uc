import { defineStore } from 'pinia'
import { basicRoutes, vueModules } from '@/router/routes'
import { useUserStore } from '@/store'
import { useTagsStore } from '@/store'
import api from '@/api'

const Layout = () => import('@/layout/index.vue')

// * 后端路由相关函数
// 根据后端传来数据构建出前端路由
const issueMenuIcons = {
  '/issue/dashboard': 'material-symbols:fact-check-outline-rounded',
  '/issue/list': 'material-symbols:format-list-bulleted-rounded',
  '/issue/config': 'material-symbols:fact-check-outline-rounded',
  '/project/config': 'material-symbols:settings-outline',
}

function menuIcon(item) {
  return issueMenuIcons[item.component] || item.icon
}

function buildRoutes(routes = []) {
  return routes.map((e) => {
    const children = Array.isArray(e.children) ? e.children : []
    const route = {
      name: e.name,
      path: e.path,
      component: Layout,
      isHidden: e.is_hidden,
      redirect: e.redirect,
      meta: {
        title: e.name,
        icon: menuIcon(e),
        order: e.order,
        keepAlive: e.keepalive,
      },
      children: [],
    }

    if (children.length > 0) {
      // 有子菜单
      route.children = children
        .map((e_child) => {
          const component = vueModules[`/src/views${e_child.component}/index.vue`]
          if (!component) return null
          return {
            name: e_child.name,
            path: e_child.path,
            component,
            isHidden: e_child.is_hidden,
            meta: {
              title: e_child.name,
              icon: menuIcon(e_child),
              order: e_child.order,
              keepAlive: e_child.keepalive,
            },
          }
        })
        .filter(Boolean)
    } else {
      // 没有子菜单，创建一个默认的子路由
      const component = vueModules[`/src/views${e.component}/index.vue`]
      if (!component) {
        return null
      }
      route.children.push({
        name: `${e.name}Default`,
        path: '',
        component,
        isHidden: true,
        meta: {
          title: e.name,
          icon: menuIcon(e),
          order: e.order,
          keepAlive: e.keepalive,
        },
      })
    }

    return route
  }).filter(Boolean)
}

function collectRoutePaths(routes = [], parentPath = '') {
  const paths = []
  routes.forEach((route) => {
    const current = route.path?.startsWith('/') ? route.path : `${parentPath}/${route.path || ''}`.replace(/\/+/g, '/')
    if (current) paths.push(current === '/' ? current : current.replace(/\/$/, ''))
    if (route.children?.length) paths.push(...collectRoutePaths(route.children, current))
  })
  return paths
}

export const usePermissionStore = defineStore('permission', {
  state() {
    return {
      accessRoutes: [],
      accessApis: [],
      accessPaths: [],
      routesLoaded: false,
    }
  },
  getters: {
    routes() {
      return basicRoutes.concat(this.accessRoutes)
    },
    menus() {
      const userStore = useUserStore()
      return this.routes
        .filter((route) => route.name && !route.isHidden)
        .filter((route) => !(route.path === '/workbench' && !userStore.isSuperUser))
    },
    apis() {
      return this.accessApis
    },
  },
  actions: {
    async generateRoutes() {
      const res = await api.getUserMenu() // 调用接口获取后端传来的菜单路由
      this.accessRoutes = buildRoutes(res.data) // 处理成前端路由格式
      this.accessPaths = collectRoutePaths(this.accessRoutes)
      const tagsStore = useTagsStore()
      tagsStore.sanitizeByMenus(this.menus)
      return this.accessRoutes
    },
    async getAccessApis() {
      const res = await api.getUserApi()
      this.accessApis = res.data
      return this.accessApis
    },
    resetPermission() {
      this.$reset()
    },
    setRoutesLoaded() {
      this.routesLoaded = true
    },
    canAccessPath(path) {
      const normalized = String(path || '').replace(/\/$/, '') || '/'
      return this.accessPaths.some((item) => normalized === item || normalized.startsWith(`${item}/`))
    },
  },
})
