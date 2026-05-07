<template>
  <router-link h-60 f-c-c to="/">
    <img v-if="appStore.siteLogo" :src="appStore.siteLogo" alt="logo" style="height: 36px; width: 36px" />
    <icon-custom-logo v-else text-36 color-primary></icon-custom-logo>
    <h2
      v-show="!appStore.collapsed"
      ml-2
      mr-8
      max-w-220
      flex-shrink-0
      text-14
      font-bold
      color-primary
      whitespace-nowrap
      overflow-hidden
      text-ellipsis
    >
      {{ appStore.siteTitle || title }}
    </h2>
  </router-link>
</template>

<script setup>
import { useAppStore } from '@/store'
const title = import.meta.env.VITE_TITLE

const appStore = useAppStore()
</script>
