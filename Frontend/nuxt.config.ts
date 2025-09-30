// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
    compatibilityDate: '2025-07-15',
    devtools: {enabled: true},
    modules: ['@nuxt/eslint', '@nuxt/image', '@nuxt/ui'],
    css: ['../assets/css/main.css'],
    ssr: false,
    runtimeConfig: {
        public: {
            // Override at runtime with NUXT_PUBLIC_API_BASE
            apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:11001'
        }
    },
    vite: {
        // Better support for Tauri CLI output
        clearScreen: false,
        // Enable environment variables
        // Additional environment variables can be found at
        // https://v2.tauri.app/reference/environment-variables/
        envPrefix: ['VITE_', 'TAURI_'],
        server: {
            // Tauri requires a consistent port
            strictPort: true,
        },
    },
    // Avoids error [unhandledRejection] EMFILE: too many open files, watch
    ignore: ['**/src-tauri/**'],
})