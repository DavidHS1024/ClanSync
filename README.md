# ⚔️ ClanSync

> **Sistema automatizado de gestión y auditoría de datos para Clash of Clans.**

ClanSync es un motor de sincronización de datos en segundo plano que conecta la API oficial de Clash of Clans con Google Sheets. Su objetivo es transformar la administración manual de un clan en un proceso automatizado, relacional y libre de fricciones, permitiendo a los líderes auditar la participación y optimizar el rendimiento del clan en eventos competitivos.

## 🛠️ Arquitectura Técnica

El sistema está construido en **Python** y opera bajo una arquitectura de extracción e inyección de datos (ETL) programada:
- **Data Source:** [Clash of Clans API](https://developer.clashofclans.com/) (vía RoyaleAPI Proxy para evasión de IP dinámica).
- **Almacenamiento:** Google Sheets API (Configurado como base de datos relacional).
- **Automatización:** GitHub Actions (Cron Jobs).

## ✨ Características Actuales

- **Sincronización de Asaltos de la Capital:** Extracción automática de los ataques realizados y el oro saqueado por cada miembro durante el fin de semana.
- **Base de Datos Relacional (Soft Delete):** Mantenimiento de registros históricos sin romper las dependencias de datos al expulsar o modificar el estado de un miembro.
- **Dashboard de Auditoría:** Paneles generados mediante consultas SQL-like (`QUERY` en Sheets) para identificar miembros inactivos en tiempo real.

## 🚀 Roadmap y Futuras Mejoras

ClanSync se encuentra en desarrollo activo. Las siguientes características están proyectadas para futuras versiones:

- [ ] **Módulo de Juegos del Clan:** Automatización de la extracción de puntos mensuales.
- [ ] **Módulo de Ligas de Guerras de Clanes (CWL):** Tracking de estrellas, porcentaje de destrucción y defensas por jugador.
- [ ] **Alerta de Inactividad (Discord Bot):** Integración de un Webhook para enviar notificaciones automáticas al servidor de Discord del clan con la "lista negra" semanal de expulsiones.
- [ ] **Análisis de Rendimiento:** Algoritmo para identificar patrones de mejora en atacantes y optimización en los diseños de bases de guerra asimétricas.

## ⚙️ Configuración y Despliegue

Este proyecto utiliza variables de entorno protegidas para las credenciales. Para desplegar tu propia instancia:

1. Clona el repositorio.
2. Configura las variables de entorno (`COC_TOKEN`, `SHEET_ID`, `CLAN_TAG`, `GOOGLE_CREDENTIALS_JSON`).
3. El despliegue continuo está manejado por el flujo de trabajo en `.github/workflows/sync.yml`.

---
*Desarrollado por Jhosuel Haro (JH).*