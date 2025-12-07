[← Volver al README Principal](../README.md)

# 🧠 Estrategia de Trading e Inteligencia Artificial

Este documento explica la lógica financiera y algorítmica detrás de las decisiones del bot.

## 🤖 El Modelo de IA: Random Forest
Se utiliza un **Random Forest Classifier** de `scikit-learn`. 
- **¿Por qué Random Forest?**: Es robusto contra el sobreajuste (overfitting) y maneja bien relaciones no lineales entre múltiples indicadores técnicos.
- **Entrenamiento Universal**: A diferencia de otros bots que entrenan un modelo por moneda, aquí se implementa un **Modelo Universal**. El modelo se entrena con datos combinados de BTC, ETH, SOL, etc. Esto permite a la IA aprender patrones generales del mercado cripto ("sentimiento"), haciéndola más adaptable a monedas nuevas.

### Features (Variables de Entrada)
La IA no "ve" el gráfico, procesa estos números derivados:
1.  **Tendencia**: Medias Móviles (SMA 20, SMA 50, EMA 12) y **MACD**.
2.  **Momento**: **RSI** (Índice de Fuerza Relativa) para detectar sobrecompra/sobreventa.
3.  **Volatilidad**: **Bandas de Bollinger** (ancho de banda) y desviación estándar de retornos.
4.  **Lag Features**: Las mismas variables de hace 1, 2 y 3 periodos (para que la IA entienda la "historia" reciente).

## 🛡️ Gestión de Riesgo (Risk Management)
La preservación de capital es la prioridad #1. El sistema implementa reglas estrictas que la IA no puede saltarse.

### 1. Filtro de Baja Volatilidad
*   **Regla**: Si el mercado está "muerto" (movimiento casi nulo), **NO SE OPERA**.
*   **Razón**: En mercados planos, las comisiones y el "ruido" se comen las ganancias. El bot espera a que haya acción.

### 2. Stops Dinámicos (ATR)
No se usan stops fijos (ej. siempre vender a -2%). Se utiliza el **ATR (Average True Range)**.
*   **Stop Loss**: Se coloca a `N * ATR` por debajo del precio de entrada. Si el mercado es muy volátil, el stop se aleja para dar "aire". Si es calmado, se ajusta para proteger ganancias.
*   **Take Profit**: Similar, basado en múltiplos de ATR.

### 3. Límites de Posición
*   **Max Open Positions**: Configurable (defecto: 3). Nunca expone todo el capital a la vez.
*   **Risk Per Trade**: Se calcula el tamaño de la posición para no arriesgar más de un X% del balance total en una sola operación mala.

## 🔄 El Scanner Multi-Moneda
Cada ciclo (aprox. 1 minuto), analiza todos los pares configurados.
1.  Obtiene predicciones para todos.
2.  Las clasifica por **Probabilidad de Éxito** (Confidence).
3.  Si tiene hueco en el portafolio, elige la mejor oportunidad disponible.
