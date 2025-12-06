# Simulación de Bot de Trading con IA

Este proyecto es un sistema completo de simulación de trading algorítmico diseñado para cuentas de capital pequeño. Integra Inteligencia Artificial (Random Forest), gestión de riesgo profesional y un dashboard de visualización en tiempo real.

## Características Principales
- **Motor de IA**: Predicción de dirección del mercado basada en indicadores técnicos (RSI, SMA, EMA, Volatilidad).
- **Gestión de Riesgo**: Sistema estricto con Stop Loss, Take Profit y filtro de volatilidad para proteger el capital.
- **Paper Trading Realista**: Simulación en tiempo real conectada a datos de mercado en vivo (Yahoo Finance / Binance).
- **Dashboard Profesional**: Interfaz web con gráficos de TradingView y métricas de rendimiento en vivo.
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
- `symbol`: Par a operar (Nota: Usar formato `BTC-USD` para Yahoo Finance).
- `risk_per_trade`: % de capital a arriesgar por operación (ej: 0.02 = 2%).
- `initial_capital`: Tu capital simulado inicial.

## Notas Importantes
- **Datos**: Por defecto usa Yahoo Finance (gratis). Puede tener un ligero retraso respecto a Binance real.
- **Gráficos**: Si el gráfico sale en blanco, asegúrate de tener conexión a internet para cargar la librería de TradingView.

---
*Descargo de responsabilidad: Este software es una herramienta educativa de simulación. El trading de criptomonedas conlleva un alto riesgo de pérdida de capital.*
