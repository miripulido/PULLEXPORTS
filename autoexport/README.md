# AutoExport — Setup completo (100% gratis)

## Qué hace esto
- **Scraper Python** que busca coches cada día en AutoScout24, mobile.de, Kleinanzeigen y leboncoin
- **GitHub Actions** lo ejecuta automáticamente cada mañana a las 8:00 (España)
- **Dashboard HTML** que muestra los resultados con filtros, cálculo de margen y score de oportunidad
- **Coste total: 0€**

---

## PASO 1 — Crear repositorio en GitHub (5 min)

1. Ve a https://github.com y crea una cuenta si no tienes
2. Haz clic en **New repository**
3. Nombre: `autoexport` — marca como **Private** (para que sea solo tuyo)
4. Sube todos estos archivos manteniendo la estructura de carpetas:
   ```
   autoexport/
   ├── .github/workflows/daily_scraper.yml
   ├── scraper/
   │   ├── scraper.py
   │   └── requirements.txt
   ├── dashboard/
   │   └── index.html
   └── supabase_schema.sql
   ```

---

## PASO 2 — Crear base de datos gratuita en Supabase (10 min)

1. Ve a https://supabase.com y crea una cuenta gratuita
2. Haz clic en **New project** — elige un nombre y contraseña
3. Espera 2 minutos a que se cree
4. Ve a **SQL Editor** (menú izquierdo) y pega el contenido de `supabase_schema.sql`
5. Haz clic en **Run** — esto crea la tabla `cars`
6. Ve a **Settings → API** y copia:
   - **Project URL** (algo como `https://xxxx.supabase.co`)
   - **anon public key** (para el dashboard)
   - **service_role key** (para el scraper — ¡no la compartas!)

---

## PASO 3 — Configurar los secretos en GitHub (5 min)

En tu repositorio de GitHub:
1. Ve a **Settings → Secrets and variables → Actions**
2. Añade dos secretos:
   - `SUPABASE_URL` → pega tu Project URL
   - `SUPABASE_KEY` → pega tu **service_role key**

---

## PASO 4 — Configurar el dashboard (2 min)

Abre `dashboard/index.html` y edita las líneas 1-4 del bloque CONFIG:

```javascript
const CONFIG = {
  supabase_url: "https://TUPROYECTO.supabase.co",  // ← tu URL
  supabase_key: "eyJhbGci...",                      // ← tu anon key
  local_json: "../scraper/cars_data.json",
  import_costs: 6000,
};
```

---

## PASO 5 — Activar GitHub Pages para el dashboard (3 min)

1. En tu repositorio: **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / carpeta: `/dashboard`
4. Guarda — en 1-2 minutos tendrás tu dashboard en:
   `https://TU_USUARIO.github.io/autoexport/`

---

## PASO 6 — Ejecutar el scraper por primera vez

1. Ve a tu repositorio → pestaña **Actions**
2. Haz clic en **AutoExport Daily Scraper**
3. Haz clic en **Run workflow** → **Run workflow**
4. Espera ~15-20 minutos a que termine
5. Abre tu dashboard — deberías ver los coches

---

## Automatización diaria

El workflow está programado para ejecutarse cada día a las **06:00 UTC (08:00 España)**.
Puedes cambiarlo editando `.github/workflows/daily_scraper.yml`:
```yaml
- cron: "0 6 * * *"   # 06:00 UTC = 08:00 España
```

---

## Estructura de costes

| Servicio | Plan | Límite gratuito | Coste |
|----------|------|-----------------|-------|
| GitHub (repo + Actions) | Free | 2.000 min/mes | 0€ |
| Supabase | Free | 500MB / 50.000 req/día | 0€ |
| GitHub Pages | Free | Ilimitado | 0€ |
| **Total** | | | **0€** |

El scraper tarda ~15 min/día = ~450 min/mes. Bien dentro del límite gratuito.

---

## Añadir más fuentes en el futuro

Para añadir una nueva fuente de coches, añade una función en `scraper.py`:
```python
def scrape_NUEVA_WEB(model: str) -> list:
    # ... tu código de scraping
    return results

# Y llámala en run():
cars_new = scrape_NUEVA_WEB(model)
raw = cars_as + cars_mo + cars_kl + cars_new
```

## Modelos objetivo

Edita la lista `TARGET_MODELS` en `scraper.py` para buscar exactamente los coches que quieres.
