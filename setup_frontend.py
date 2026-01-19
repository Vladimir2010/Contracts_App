import os
import json

FRONTEND_DIR = r"c:\Users\Dell\PycharmProjects\Contracts_App\Contracts_App_Web\frontend"
SRC_DIR = os.path.join(FRONTEND_DIR, "src")

os.makedirs(SRC_DIR, exist_ok=True)

# package.json
pkg = {
  "name": "contracts-app-web",
  "private": True,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@heroicons/react": "^2.1.1",
    "axios": "^1.6.7"
  },
  "devDependencies": {
    "@types/react": "^18.2.56",
    "@types/react-dom": "^18.2.19",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.35",
    "tailwindcss": "^3.4.1",
    "vite": "^5.1.4"
  }
}
with open(os.path.join(FRONTEND_DIR, "package.json"), "w") as f:
    json.dump(pkg, f, indent=2)

# vite.config.js
vite_conf = """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
"""
with open(os.path.join(FRONTEND_DIR, "vite.config.js"), "w") as f:
    f.write(vite_conf)

# tailwind.config.js
tw_conf = """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
"""
with open(os.path.join(FRONTEND_DIR, "tailwind.config.js"), "w") as f:
    f.write(tw_conf)

# postcss.config.js
pc_conf = """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
"""
with open(os.path.join(FRONTEND_DIR, "postcss.config.js"), "w") as f:
    f.write(pc_conf)

# index.html
idx_html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Contracts App Professional</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""
with open(os.path.join(FRONTEND_DIR, "index.html"), "w") as f:
    f.write(idx_html)

# src/main.jsx
main_jsx = """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
"""
with open(os.path.join(SRC_DIR, "main.jsx"), "w") as f:
    f.write(main_jsx)

# src/index.css
idx_css = """@tailwind base;
@tailwind components;
@tailwind utilities;

body {
    background-color: #f3f4f6;
    color: #1f2937;
}
"""
with open(os.path.join(SRC_DIR, "index.css"), "w") as f:
    f.write(idx_css)

# src/App.jsx (Basic UI)
# Using 'Full Name' (col 3), 'Model' (col 17), 'Serial' (col 18) based on main.py columns
app_jsx = """import { useState, useEffect } from 'react'
import axios from 'axios'

function App() {
  const [devices, setDevices] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    axios.get('/api/devices')
      .then(res => {
        setDevices(res.data.data)
        setLoading(false)
      })
      .catch(err => {
        console.error(err)
        setLoading(false)
      })
  }, [])

  return (
    <div className="min-h-screen p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-slate-800">Contracts App Professional</h1>
        <p className="text-slate-500">Web Version</p>
      </header>

      <main className="bg-white rounded-lg shadow-xl overflow-hidden">
        <div className="p-6 border-b border-gray-100 bg-gray-50 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-gray-700">Списък устройства</h2>
            <span className="bg-blue-100 text-blue-800 text-xs font-semibold px-2 py-1 rounded-full">
                {devices.length} записа
            </span>
        </div>
        
        {loading ? (
          <div className="p-10 text-center text-gray-500">Зареждане на данни...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Фирма</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ЕИК</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Модел</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Сериен №</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {devices.map((d, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{d[3]}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{d[4]}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{d[17]}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{d[18]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
"""
with open(os.path.join(SRC_DIR, "App.jsx"), "w", encoding="utf-8") as f:
    f.write(app_jsx)

print("Frontend setup complete.")
