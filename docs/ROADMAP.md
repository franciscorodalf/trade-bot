# 🗺️ Roadmap del Proyecto

Este documento describe la visión a futuro del **AI Trading Bot**. El desarrollo se divide en fases para asegurar la estabilidad antes de escalar.

## ✅ Fase 1: Cimientos (Completada)
- [x] Motor de IA Random Forest Operativo.
- [x] Conexión con Binance (Datos de mercado).
- [x] Sistema de Paper Trading (Simulación de saldo y órdenes).
- [x] API FastAPI y Dashboard Web básico.
- [x] Soporte Multi-Moneda y Scanner Universal.
- [x] Implementación de MACD y Bollinger Bands.

## ✅ Fase 1.5: DevOps y UI Profesional (Completada)
- [x] Dockerización completa (`Dockerfile` + `docker-compose.yml`).
- [x] `Makefile` con comandos de desarrollo y despliegue.
- [x] Soporte de variables de entorno (`.env`).
- [x] `.gitignore` profesional.
- [x] Rediseño completo del Dashboard (dark theme profesional, glassmorphism, animaciones).
- [x] README.md de nivel portfolio para LinkedIn.

## 🚧 Fase 2: Velocidad y Eficiencia (Próxima)
El objetivo es reducir la latencia de análisis para capturar oportunidades fugaces.
- [ ] **Data Fetching Asíncrono**: Migrar de `ccxt` síncrono a `ccxt.async_support` + `asyncio`.
    - *Meta*: Reducir el tiempo de escaneo total de ~20s a <2s.
- [ ] **WebSockets**: Recibir precios en tiempo real (streaming) en lugar de pedir velas cada minuto.

## 📅 Fase 3: Inteligencia Avanzada
Darle más herramientas al modelo para entender el contexto.
- [ ] **Análisis de Sentimiento**: Integrar noticias o tweets (API de Twitter/X o CryptoNews) como feature.
- [ ] **Deep Learning**: Experimentar con redes **LSTM** (Long Short-Term Memory) para secuencias temporales complejas.
- [ ] **Backtesting Engine**: Módulo dedicado para probar estrategias con datos de años pasados en segundos.

## 🚀 Fase 4: Producción y Live Trading
Solo cuando el sistema demuestre rentabilidad consistente en simulación.
- [ ] **Gestión de API Keys**: Encriptación segura de claves privadas.
- [x] **Dockerización**: `Dockerfile` y `docker-compose` para despliegue en VPS (AWS/DigitalOcean).
- [ ] **Notificaciones**: Telegram/Discord bot para avisar al móvil cuando se abre una operación.
- [ ] **CI/CD Pipeline**: GitHub Actions para tests automáticos y despliegue.
