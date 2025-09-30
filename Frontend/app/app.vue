<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, nextTick } from 'vue'

const config = useRuntimeConfig()
const API_BASE = (config.public?.apiBase as string) || 'http://localhost:11001'

// Single source of truth for the intermediate/input directory used by BOTH Start & Organize
const intermediateDir = ref<string>(
  localStorage.getItem('intermediateDir') || './data/intermediate'
)

// Output DB path
const organizeOutputDb = ref<string>(
  localStorage.getItem('organizeOutputDb') || './data/out/scraper.db'
)

watch(intermediateDir, (v) => localStorage.setItem('intermediateDir', v))
watch(organizeOutputDb, (v) => localStorage.setItem('organizeOutputDb', v))

const logs = ref<string[]>([])
const isStarting = ref(false)
const isStopping = ref(false)
const isOrganizing = ref(false)
const status = ref<string>('idle')

const logPane = ref<HTMLElement | null>(null)
let timer: any = null

// Detect Tauri at runtime; only call dialog APIs when available
const isTauri = true

async function browseIntermediateDir() {
  try {
    if (isTauri) {
      const { open } = await import('@tauri-apps/plugin-dialog')
      const selected = await open({ directory: true, multiple: false })
      if (typeof selected === 'string' && selected) {
        intermediateDir.value = selected
      }
    } else {
      // Fallback: try browser directory picker; may not give absolute path
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      if (window.showDirectoryPicker) {
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-ignore
        const handle = await window.showDirectoryPicker()
        if (handle?.name) {
          // As browsers cannot provide absolute paths, keep name as hint
          intermediateDir.value = handle.name
        }
      }
    }
  } catch (e) {
    // ignore
  }
}

async function browseOutputDb() {
  try {
    if (isTauri) {
      const { save } = await import('@tauri-apps/plugin-dialog')
      const suggestedName = organizeOutputDb.value?.split('/').pop() || 'scraper.db'
      const selected = await save({ defaultPath: organizeOutputDb.value, filters: [{ name: 'SQLite', extensions: ['db', 'sqlite'] }], title: 'Choose output DB path' })
      if (selected) organizeOutputDb.value = selected
    } else {
      // Fallback: prompt
      const v = prompt('Enter output DB path', organizeOutputDb.value)
      if (v) organizeOutputDb.value = v
    }
  } catch (e) {
    // ignore
  }
}

async function fetchLogs() {
  try {
    const res = await $fetch<{ stdout: string[] }>(`${API_BASE}/stdout`, {
      query: { lines: 30 },
    })
    logs.value = res?.stdout || []
    await nextTick()
    if (logPane.value) {
      logPane.value.scrollTop = logPane.value.scrollHeight
    }
  } catch (e) {
    // silently ignore polling errors
  }
}

async function startScraping() {
  isStarting.value = true
  try {
    const res = await $fetch<{ status: string; pid?: number; message?: string }>(
      `${API_BASE}/start-scraping`,
      {
        method: 'POST',
        body: { intermediate_dir: intermediateDir.value },
      }
    )
    status.value = res.status + (res.pid ? ` (pid ${res.pid})` : '')
  } catch (e: any) {
    status.value = `start error: ${e?.data?.detail || e?.message || e}`
  } finally {
    isStarting.value = false
    fetchLogs()
  }
}

async function stopScraping() {
  isStopping.value = true
  try {
    const res = await $fetch<{ status: string; message?: string }>(
      `${API_BASE}/stop-scraping`,
      {
        method: 'POST',
      }
    )
    status.value = res.status
  } catch (e: any) {
    status.value = `stop error: ${e?.data?.detail || e?.message || e}`
  } finally {
    isStopping.value = false
    fetchLogs()
  }
}

async function organize() {
  isOrganizing.value = true
  try {
    const res = await $fetch<{ status: string; output_db?: string; message?: string }>(
      `${API_BASE}/organize`,
      {
        method: 'POST',
        body: { input_dir: intermediateDir.value, output_db: organizeOutputDb.value },
      }
    )
    status.value = res.status + (res.output_db ? ` (${res.output_db})` : '')
  } catch (e: any) {
    status.value = `organize error: ${e?.data?.detail || e?.message || e}`
  } finally {
    isOrganizing.value = false
    fetchLogs()
  }
}

onMounted(() => {
  fetchLogs()
  timer = setInterval(fetchLogs, 1500)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <UApp>
    <UContainer class="py-6">
    <div class="grid gap-6">
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-semibold">Scraper Controls</h2>
            <UBadge color="secondary" variant="soft">{{ status }}</UBadge>
          </div>
        </template>

        <div class="grid gap-4">
          <div class="grid md:grid-cols-2 gap-4 items-end">
            <UFormField label="Intermediate Dir (used by Start & Organize)">
              <div class="flex gap-2">
                <UInput v-model="intermediateDir" placeholder="./data/intermediate" icon="i-heroicons-folder" class="flex-1" />
                <UButton color="secondary" variant="solid" icon="i-heroicons-folder-open" @click="browseIntermediateDir">Browse</UButton>
              </div>
            </UFormField>
            <div class="flex gap-2">
              <UButton color="primary" :loading="isStarting" @click="startScraping" icon="i-heroicons-play">
                Start Scraping
              </UButton>
              <UButton color="error" variant="solid" :loading="isStopping" @click="stopScraping" icon="i-heroicons-stop">
                Stop
              </UButton>
            </div>
          </div>

          <div class="grid md:grid-cols-3 gap-4 items-end">
            <UFormField label="Organize Input Dir (same as Intermediate Dir)">
              <UInput v-model="intermediateDir" icon="i-heroicons-folder" disabled />
            </UFormField>
            <UFormField label="Output DB Path">
              <div class="flex gap-2">
                <UInput v-model="organizeOutputDb" placeholder="./data/out/scraper.db" icon="i-heroicons-document-text" class="flex-1" />
                <UButton color="secondary" variant="solid" icon="i-heroicons-document-plus" @click="browseOutputDb">Save As</UButton>
              </div>
            </UFormField>
            <div class="flex">
              <UButton color="primary" :loading="isOrganizing" @click="organize" icon="i-heroicons-arrow-down-tray" class="w-full">
                Organize Dataset
              </UButton>
            </div>
          </div>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <h3 class="font-medium">Terminal Output</h3>
            <div class="flex gap-2">
              <UButton color="secondary" variant="ghost" icon="i-heroicons-arrow-path" @click="fetchLogs">Refresh</UButton>
              <UButton color="secondary" variant="ghost" icon="i-heroicons-trash" @click="logs = []">Clear</UButton>
            </div>
          </div>
        </template>
        <div ref="logPane" class="terminal border rounded-md p-3 font-mono text-sm bg-gray-950 text-gray-200 overflow-auto h-80">
          <pre class="whitespace-pre-wrap m-0">{{ logs.join('\n') }}</pre>
        </div>
      </UCard>
    </div>
  </UContainer>
  </UApp>
</template>

<style scoped>
.terminal {
  /* Ensure smooth auto-scroll for new logs */
  scroll-behavior: smooth;
}
</style>