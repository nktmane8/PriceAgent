import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development the API runs on :3000 and Vite proxies /api to it. In production Node serves web/dist itself.
export default defineConfig({ plugins: [react()], server: { proxy: { '/api': 'http://localhost:3000' } } });
