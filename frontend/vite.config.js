// Import the tool that defines Vite settings
import { defineConfig } from 'vite'
// Import the plugin that lets Vite understand React
import react from '@vitejs/plugin-react'
// Import the plugin that powers Tailwind styling
import tailwindcss from '@tailwindcss/vite'

// Export the settings for our project
export default defineConfig({
  // Turn on React and Tailwind
  plugins: [react(), tailwindcss()],
  // Run the dev server on port 5173
  server: { port: 5173 },
})