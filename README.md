# 🦅 AI Quantitative Trading Bot

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-green.svg)
![Binance](https://img.shields.io/badge/Data-Binance-yellow.svg)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)
![Status](https://img.shields.io/badge/Status-Beta%20(Paper%20Trading)-orange.svg)

---
---

**Sistema de Trading Algorítmico Automatizado (v2.0)**

Este proyecto implementa un bot de trading cuantitativo de nueva generación diseñado para operar en mercados de criptomonedas con precisión quirúrgica.

A diferencia de los bots tradicionales, este sistema **"Anti-Fragile"** combina:
1.  **Inteligencia Artificial (Random Forest)**: Predicción de movimientos basada en aprendizaje histórico.
2.  **Arquitectura Reactiva (AsyncIO)**: Escaneo paralelo de múltiples pares en milisegundos.
3.  **Interfaz Premium**: Dashboard en tiempo real con diseño Glassmorphism y métricas profesionales.

---

## 🚀 Novedades v2.0 (Titanium Update)

Hemos reconstruido el núcleo para ser más rápido, inteligente y bonito.

*   **⚡ Motor Asíncrono Híbrido**: El bot ahora escanea 12+ pares simultáneamente usando `ccxt.async`. 
    *   *Ciclo de Escaneo*: Reducido de 50s a **~8s**.
*   **👁️ Frontend Glassmorphism**: Nueva interfaz visual inspirada en terminales Cyberpunk.
    *   *Live Charts*: Gráficos interactivos con marcadores de compra/venta.
    *   *Confidence Bars*: Visualización clara de la certeza de la IA.
    *   *Terminal Logs*: Feedback del sistema en tiempo real.
*   **🛡️ Resiliencia "Anti-Pánico"**: Lógica de gestión de errores (Exponential Backoff) y protección contra Rate Limits.
    *   *Self-Healing*: Si la API falla, el bot espera inteligentemente en lugar de crashear.
*   **🔐 Seguridad Enterprise**: Soporte nativo para API Keys de Solo Lectura (binance).

---

## 📚 Documentación Exclusiva

Para entender a fondo cómo funciona cada engranaje, consulta la documentación detallada:

-   **[🏗️ Arquitectura Técnica](docs/ARCHITECTURE.md)**: Cómo se comunican el Bot, la API y la Web.
-   **[🧠 Estrategia e IA](docs/STRATEGY.md)**: Explicación del modelo predictivo, indicadores (MACD, Bollinger) y gestión de riesgo.
-   **[🗺️ Roadmap](docs/ROADMAP.md)**: El plan de futuro y las próximas funcionalidades.

---

## ✨ Características Clave

*   **🔍 Scanner de Mercado IA**: Monitorización en tiempo real de 6+ pares (BTC, ETH, SOL...) buscando patrones de alta probabilidad.
*   **🧠 Inteligencia Colectiva**: Modelo "Universal" entrenado con datos de todo el mercado, capaz de adaptarse a diferentes activos.
*   **🛡️ Gestión de Riesgo Profesional**: Cálculo dinámico de posiciones y Stop Loss basados en la volatilidad (ATR). Nunca se arriesga más de lo configurado.
*   **📉 Simulación Realista (Paper Trading)**: Opera con precios reales de **Binance Futures** sin arriesgar dinero real. Perfecto para validar estrategias.
*   **📊 Command Center**: Dashboard web interactivo para visualizar las decisiones de la IA, el portafolio y los gráficos en vivo.

---

## 🚀 Quick Start

Sigue estos pasos para levantar tu propio laboratorio de trading en minutos.

### Prerrequisitos
-   Python 3.9+
-   Git

### Instalación

1.  **Clonar el repositorio**:
    ```bash
    git clone https://github.com/tu-usuario/trade-bot.git
    cd trade-bot
    ```

2.  **Preparar entorno**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # En Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Configuración**:
    El archivo `config.json` ya viene pre-configurado para simulación. Puedes editar `symbols` para añadir más monedas.

4.  **Entrenar a la IA**:
    Antes de operar, el cerebro debe aprender.
    ```bash
    python3 bot/train_model.py
    ```

### Ejecutar el Sistema

Necesitarás **3 terminales** abiertas (o usar tmux/docker en el futuro):

*   **Terminal 1 (El Bot)**:
    ```bash
    source venv/bin/activate
    python3 bot/paper_trading.py
    ```

*   **Terminal 2 (La API)**:
    ```bash
    source venv/bin/activate
    uvicorn api.main:app --reload
    ```

*   **Terminal 3 (El Dashboard)**:
    ```bash
    cd web
    python3 -m http.server 5500
    ```
    👉 Abre tu navegador en: `http://localhost:5500`

---

## ⚠️ Disclaimer

**Este software es una herramienta con fines educativos y de investigación.** El trading con criptomonedas conlleva un riesgo significativo de pérdida de capital. El rendimiento pasado del modelo no garantiza resultados futuros. Úsalo bajo tu propia responsabilidad.

---
*Desarrollado con ❤️ y mucho ☕.*
