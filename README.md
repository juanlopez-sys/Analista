# 🚀 Sistema Analista Crypto — Guía de despliegue

## Estructura del repositorio

```
crypto-analyst/
├── backend/                  ← FastAPI (Python)
│   ├── api.py
│   ├── claude_analyst.py
│   ├── config.py
│   ├── data_collector.py
│   ├── database.py
│   ├── error_handler.py
│   ├── news_collector.py
│   ├── positions.py
│   ├── validators.py
│   └── requirements.txt
├── frontend/                 ← HTML + CSS + JS estático
│   ├── index.html
│   ├── js/
│   │   ├── actions.js
│   │   ├── api.js
│   │   ├── chat.js
│   │   ├── main.js
│   │   ├── nav.js
│   │   ├── security.js
│   │   └── ui.js
│   └── styles/
│       ├── base.css
│       ├── components.css
│       ├── layout.css
│       └── panels.css
├── render.yaml               ← Configuración de Render
├── .env.example              ← Plantilla de variables de entorno
├── .gitignore
└── README.md
```

---

## 1. Configurar Supabase

1. Ve a [supabase.com](https://supabase.com) y crea un proyecto nuevo
2. Espera a que el proyecto se inicialice (~2 minutos)
3. Ve a **Project Settings → Database → Connection string → URI**
4. Copia la URI en modo **Session** (puerto 5432)
5. Guarda esta URI — la necesitarás en el paso 3

---

## 2. Subir el código a GitHub

```bash
# En la raíz del proyecto
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/crypto-analyst.git
git push -u origin main
```

---

## 3. Crear los servicios en Render

### 3a. Backend (Web Service)

1. Ve a [render.com](https://render.com) → **New → Web Service**
2. Conecta tu repositorio de GitHub
3. Configura:
   - **Name**: `crypto-analyst-api`
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api:app --host 0.0.0.0 --port $PORT`
4. En **Environment Variables**, agrega:
   ```
   CLAUDE_API_KEY         = sk-ant-...
   BINANCE_API_KEY        = tu_key
   BINANCE_API_SECRET     = tu_secret
   CRYPTOPANIC_API_KEY    = tu_key
   DATABASE_URL           = postgresql://postgres:...@db.xxx.supabase.co:5432/postgres
   RENDER                 = true
   FRONTEND_URL           = (dejar vacío por ahora, lo completas después)
   ```
5. Clic en **Create Web Service**
6. Espera el deploy (~3-5 min). Cuando termine, copia la URL, ej: `https://crypto-analyst-api.onrender.com`

### 3b. Inicializar la base de datos

Una vez el backend esté corriendo, llama este endpoint UNA sola vez para crear las tablas en Supabase:

```
GET https://crypto-analyst-api.onrender.com/api/init-db
```

O desde la terminal de Render (Shell):
```bash
python -c "from database import create_tables; create_tables()"
```

### 3c. Frontend (Static Site)

1. Ve a **New → Static Site**
2. Conecta el mismo repositorio
3. Configura:
   - **Name**: `crypto-analyst-app`
   - **Root Directory**: `frontend`
   - **Build Command**:
     ```
     sed -i 's|__BACKEND_URL__|https://crypto-analyst-api.onrender.com|g' index.html && sed -i 's|__BACKEND_URL__|https://crypto-analyst-api.onrender.com|g' js/api.js
     ```
     ⚠️ Reemplaza `https://crypto-analyst-api.onrender.com` con tu URL real del paso 3a
   - **Publish Directory**: `.`
4. Clic en **Create Static Site**
5. Cuando termine, copia la URL, ej: `https://crypto-analyst-app.onrender.com`

### 3d. Completar la configuración de CORS

Vuelve al **Web Service** (backend) y agrega la variable de entorno:
```
FRONTEND_URL = https://crypto-analyst-app.onrender.com
```
Luego haz **Manual Deploy** para que tome el nuevo valor.

---

## 4. Uso local

```bash
# Clonar
git clone https://github.com/TU_USUARIO/crypto-analyst.git
cd crypto-analyst

# Backend
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Crear .env (copia .env.example y llena los valores)
cp ../.env.example .env

# Inicializar BD local
python database.py

# Arrancar el servidor
python api.py
# → http://localhost:8000/static  (sirve el frontend automáticamente en local)
```

---

## Variables de entorno requeridas

| Variable | Dónde obtenerla |
|---|---|
| `CLAUDE_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `BINANCE_API_KEY` | [binance.com → API Management](https://www.binance.com/en/my/settings/api-management) |
| `BINANCE_API_SECRET` | Mismo lugar que la key |
| `CRYPTOPANIC_API_KEY` | [cryptopanic.com/developers/api](https://cryptopanic.com/developers/api/) (opcional) |
| `DATABASE_URL` | Supabase → Project Settings → Database → URI |
| `FRONTEND_URL` | URL de tu Static Site en Render |
