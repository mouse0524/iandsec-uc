<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Quill from 'quill'
import 'quill/dist/quill.snow.css'
import { sanitizeHtml } from '@/utils'

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  placeholder: {
    type: String,
    default: '请输入内容',
  },
  minHeight: {
    type: Number,
    default: 180,
  },
  maxHeight: {
    type: Number,
    default: 420,
  },
})

const emit = defineEmits(['update:modelValue'])

const editorRef = ref(null)
let quill = null
let syncing = false
let handleTextChange = null

function normalizeEditorHtml(value = '') {
  return sanitizeHtml(String(value || ''))
}

onMounted(() => {
  if (!editorRef.value) return
  quill = new Quill(editorRef.value, {
    theme: 'snow',
    placeholder: props.placeholder,
    modules: {
      toolbar: [
        [{ header: [1, 2, 3, false] }],
        [{ size: ['small', false, 'large', 'huge'] }],
        ['bold', 'italic', 'underline', 'strike'],
        [{ align: [] }],
        [{ list: 'ordered' }, { list: 'bullet' }],
        [{ color: [] }, { background: [] }],
        ['blockquote', 'code-block'],
        ['clean'],
      ],
    },
  })

  quill.root.style.minHeight = `${props.minHeight}px`
  quill.root.style.maxHeight = `${props.maxHeight}px`
  quill.root.style.overflowY = 'auto'
  quill.root.style.boxSizing = 'border-box'
  quill.root.innerHTML = normalizeEditorHtml(props.modelValue)
  handleTextChange = () => {
    if (!quill) return
    syncing = true
    emit('update:modelValue', normalizeEditorHtml(quill.root.innerHTML))
    syncing = false
  }
  quill.on('text-change', handleTextChange)
})

watch(
  () => props.modelValue,
  (val) => {
    if (!quill || syncing) return
    if (!quill.root || !quill.root.isConnected) return
    const html = normalizeEditorHtml(val)
    if (quill.root.innerHTML !== html) {
      quill.root.innerHTML = html
    }
  }
)

onBeforeUnmount(() => {
  if (quill && handleTextChange) {
    quill.off('text-change', handleTextChange)
  }
  handleTextChange = null
  if (quill?.root) {
    quill.disable()
  }
  quill = null
})
</script>

<template>
  <div class="rich-editor-wrap">
    <div ref="editorRef"></div>
  </div>
</template>

<style scoped>
.rich-editor-wrap {
  width: 100%;
}

.rich-editor-wrap :deep(.ql-toolbar.ql-snow) {
  border-radius: 8px 8px 0 0;
  border-color: #d6dde8;
  width: 100%;
}

.rich-editor-wrap :deep(.ql-container.ql-snow) {
  border-radius: 0 0 8px 8px;
  border-color: #d6dde8;
  width: 100%;
}

.rich-editor-wrap :deep(.ql-editor) {
  overflow-y: auto;
}
</style>
