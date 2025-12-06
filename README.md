# Simulación de Bot de Trading con IA

Este proyecto es un sistema completo de simulación de trading algorítmico diseñado para cuentas de capital pequeño. Integra Inteligencia Artificial (Random Forest), gestión de riesgo profesional y un dashboard de visualización en tiempo real con logs del sistema.

## ✨ Características Principales

-   **🧠 IA Avanzada (Random Forest)**: Entrenada con datos de múltiples criptomonedas (BTC, ETH, SOL, etc.) para detectar patrones de mercado generalizados.
-   **🔍 Scanner Multi-Moneda**: Analiza en tiempo real una cesta de monedas y selecciona las mejores oportunidades automáticamente.
-   **🛡️ Gestión de Riesgo Profesional**:
    -   Nunca apuesta todo el capital (posición regulada por riesgo).
    -   Stop Loss y Take Profit dinámicos basados en la volatilidad (ATR).
-   **📉 Simulación Realista (Paper Trading)**: Conectado a **Binance Futures** para usar precios y condiciones de mercado reales.
-   **⚡ Dashboard Web**: Interfaz gráfica para ver el "cerebro" de la IA, el scanner de mercado y el rendimiento.
    - Panel de estadísticas y estado de la cuenta.
- **Arquitectura Modular**: Separación clara entre Cerebro (IA), Ejecución (Bot) y Visualización (Web/API).

## Estructura del Proyecto
```
/bot
   train_model.py    # Entrenamiento del modelo IA
   predict.py        # Inferencia y predicción
   strategy.py       # Lógica de trading (SL/TP)
   paper_trading.py  # Motor de ejecución en tiempo real
   backtest.py       # Simulación histórica
   config.json       # Configuración central (Pares, Riesgo, Capital)

/api
   main.py           # Servidor Backend (FastAPI)

/web
   index.html        # Dashboard (Frontend)
   dashboard.js      # Lógica de conexión y gráficos
```

## Instalación Paso a Paso

### 1. Preparar el Entorno
Es **crítico** usar un entorno virtual para evitar conflictos con librerías.

```bash
# Crear el entorno virtual
python3 -m venv venv

# Activar el entorno
source venv/bin/activate
```

### 2. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 3. Inicializar Base de Datos
```bash
sqlite3 database/bot.db < database/schema.sql
```

## Guía de Ejecución (Sistema Completo)

Para que el sistema funcione, necesitas abrir **3 TERMINALES** diferentes y mantenerlas abiertas.

### TERMINAL 1: La API (El Cerebro)
Este servicio conecta la base de datos con la web.
```bash
source venv/bin/activate
uvicorn api.main:app --reload
```
*Debe decir: `Uvicorn running on http://127.0.0.1:8000`*

### TERMINAL 2: El Bot (El Ejecutor)
Este script analiza el mercado y ejecuta las operaciones.
```bash
source venv/bin/activate
python3 bot/paper_trading.py
```
*Verás logs indicando que está descargando datos y operando.*

### TERMINAL 3: El Dashboard (La Visualización)
Servimos la web localmente para asegurar la mejor conectividad.
```bash
cd web
python3 -m http.server 5500
```
*Ahora abre en tu navegador:* **http://localhost:5500**

---

## Flujo de Trabajo Recomendado

1.  **Entrenamiento Inicial**: Antes de nada, entrena a la IA con datos históricos.
    ```bash
    python3 bot/train_model.py
    ```
2.  **Backtesting**: Comprueba qué tal habría funcionado tu estrategia en el pasado.
    ```bash
    python3 bot/backtest.py
    ```
3.  **Ejecución en Vivo**: Sigue los pasos de las "3 Terminales" de arriba.

## Configuración (`config.json`)
Puedes ajustar el comportamiento del bot editando este archivo:
- `symbol`: Par a operar (Recomendado: `ADA-USD` para cuentas pequeñas).
- `risk_per_trade`: % de capital a arriesgar por operación (ej: 0.02 = 2%).
- `volatility_threshold`: Filtro de actividad (ej: 0.002 para permitir más operaciones en criptos estables).
- `initial_capital`: Tu capital simulado inicial.

## Notas Importantes
- **Datos**: Por defecto usa Yahoo Finance (gratis). Puede tener un ligero retraso respecto a Binance real.
- **Logs en Vivo**: Si ves "HOLD" y "Waiting for next cycle", es el comportamiento normal. El bot está esperando la oportunidad perfecta según su entrenamiento.

---
*Descargo de responsabilidad: Este software es una herramienta educativa de simulación. El trading de criptomonedas conlleva un alto riesgo de pérdida de capital.*
