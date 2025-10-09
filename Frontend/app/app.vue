<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, nextTick, watch, computed } from 'vue'

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

// Tabs: 0 = Controls, 1 = Charts
const activeTab = ref<number>(0)

// Charts state
const histogramKind = ref<'token_count' | 'stars' | 'likes' | 'comments' | 'year_usage' | 'word_freq'>('token_count')
const textField = ref<'review_descr' | 'title'>('review_descr')
const bins = ref<number>(20)
const topN = ref<number>(30)
const chartLoading = ref(false)
const chartError = ref<string | null>(null)
const chartLabels = ref<string[]>([])
const chartValues = ref<number[]>([])
const chartFigure = ref<any | null>(null)
const plotDiv = ref<HTMLElement | null>(null)
let plotlyLoading: Promise<any> | null = null
let localPlotly: any = null

async function ensurePlotly(): Promise<any> {
  if (localPlotly) return localPlotly
  if (plotlyLoading) return plotlyLoading
  plotlyLoading = import('plotly.js-dist-min').then((m: any) => {
    localPlotly = m?.default ?? m
    try { (window as any).Plotly = localPlotly } catch {}
    return localPlotly
  })
  return plotlyLoading
}

async function renderPlotly() {
  await nextTick()
  const el = plotDiv.value as any
  if (!chartFigure.value || !el) return
  try {
    const Plotly = await ensurePlotly()
    const fig = chartFigure.value
    await Plotly.newPlot(el, fig.data ?? [], fig.layout ?? {}, { displayModeBar: false, responsive: true })
    // Ensure proper sizing after initial render and on tab switch
    setTimeout(() => { try { Plotly.Plots.resize(el) } catch {} }, 0)
  } catch (e: any) {
    chartError.value = e?.message || String(e)
  }
}

const needsTextField = computed(() => histogramKind.value === 'token_count' || histogramKind.value === 'word_freq')
const needsBins = computed(() => ['stars','likes','comments','year_usage'].includes(histogramKind.value))
const needsTopN = computed(() => histogramKind.value === 'word_freq')

async function fetchChart() {
  chartLoading.value = true
  chartError.value = null
  chartLabels.value = []
  chartValues.value = []
  try {
    const params: Record<string, any> = { kind: histogramKind.value, db: organizeOutputDb.value, fmt: 'plotly' }
    if (needsTextField.value) params.text_field = textField.value
    if (needsBins.value) params.bins = bins.value
    if (needsTopN.value) params.top_n = topN.value
    const res = await $fetch<any>(`${API_BASE}/charts/histogram`, { query: params })
    chartFigure.value = res.figure || null
    chartLabels.value = res.labels || []
    chartValues.value = (res.values as any) || []
  } catch (e: any) {
    chartError.value = e?.data?.detail || e?.message || String(e)
  } finally {
    chartLoading.value = false
  }
}

watch([histogramKind, textField, bins, topN, organizeOutputDb], () => {
  if (activeTab.value === 1) fetchChart()
})

watch(chartFigure, async (v) => {
  if (activeTab.value !== 1 || !v) return
  await nextTick()
  renderPlotly()
})
watch(activeTab, async (t) => {
  if (t === 1 && chartFigure.value) {
    await renderPlotly()
    try {
      const Plotly = await ensurePlotly()
      const el = plotDiv.value as any
      if (el && Plotly?.Plots?.resize) Plotly.Plots.resize(el)
    } catch {}
  }
})

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

let resizeListener: any = null

onMounted(() => {
  fetchLogs()
  timer = setInterval(fetchLogs, 1500)
  if (typeof window !== 'undefined') {
    resizeListener = async () => {
      try {
        const Plotly = await ensurePlotly()
        const el = plotDiv.value as any
        if (el && Plotly?.Plots?.resize) Plotly.Plots.resize(el)
      } catch {}
    }
    window.addEventListener('resize', resizeListener)
  }
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  if (typeof window !== 'undefined' && resizeListener) {
    window.removeEventListener('resize', resizeListener)
    resizeListener = null
  }
})
</script>

<template>
  <UApp>
    <UContainer class="py-6">
    <div class="mb-4 flex gap-2">
      <UButton :color="activeTab === 0 ? 'primary' : 'gray'" variant="solid" @click="activeTab = 0">Controls</UButton>
      <UButton :color="activeTab === 1 ? 'primary' : 'gray'" variant="solid" @click="activeTab = 1; fetchChart()">Charts</UButton>
      <div class="ml-auto"><UBadge color="secondary" variant="soft">{{ status }}</UBadge></div>
    </div>

    <div v-if="activeTab === 0" class="grid gap-6">
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-semibold">Scraper Controls</h2>
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

    <div v-else class="grid gap-6">
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-semibold">Charts</h2>
          </div>
        </template>
        <div class="grid md:grid-cols-4 gap-4 items-end">
          <UFormField label="Histogram">
            <USelect
              v-model="histogramKind"
              :items="[
                { label: 'Token Count (description)', value: 'token_count' },
                { label: 'Stars', value: 'stars' },
                { label: 'Likes', value: 'likes' },
                { label: 'Comments', value: 'comments' },
                { label: 'Year Usage', value: 'year_usage' },
                { label: 'Word Frequency', value: 'word_freq' }
              ]"
              option-attribute="label"
              value-attribute="value"
            />
          </UFormField>
          <UFormField v-if="needsTextField" label="Text Field">
            <USelect
              v-model="textField"
              :items="[
                { label: 'Review Description', value: 'review_descr' },
                { label: 'Title', value: 'title' }
              ]"
              option-attribute="label"
              value-attribute="value"
            />
          </UFormField>
          <UFormField v-if="needsBins" label="Bins">
            <UInput v-model.number="bins" type="number" min="1" />
          </UFormField>
          <UFormField v-if="needsTopN" label="Top N">
            <UInput v-model.number="topN" type="number" min="1" />
          </UFormField>
          <div class="flex">
            <UButton color="primary" :loading="chartLoading" @click="fetchChart" icon="i-heroicons-chart-bar">Update</UButton>
          </div>
        </div>

        <div class="mt-4">
          <div v-if="chartError" class="text-red-600">{{ chartError }}</div>
          <div v-else-if="chartLoading">Loading…</div>
          <div v-else>
            <div v-if="chartFigure">
              <div ref="plotDiv" class="w-full" style="height: 420px;"></div>
            </div>
            <div v-else-if="chartLabels.length === 0">No data</div>
            <div v-else class="space-y-1">
              <div v-for="(label, i) in chartLabels" :key="i" class="flex items-center gap-2">
                <div class="w-40 text-xs truncate" :title="label">{{ label }}</div>
                <div class="flex-1 bg-gray-200 dark:bg-gray-800 h-4 rounded">
                  <div class="bg-primary-500 h-4 rounded" :style="{ width: (Math.max(...chartValues) ? (chartValues[i] / Math.max(...chartValues) * 100) : 0) + '%' }"></div>
                </div>
                <div class="w-12 text-right text-xs">{{ chartValues[i] }}</div>
              </div>
            </div>
          </div>
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