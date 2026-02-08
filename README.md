# 🚚 Fletes Exus - Plataforma de Gestión Logística Express

Una solución integral Full-Stack diseñada para "Fletes Javier", optimizando el proceso de cotización, reserva y administración de servicios de transporte y mudanzas con una experiencia de usuario premium.

## 🌟 Características Principales

### 1. **Motor de Cotización Inteligente**
- **Sugerencias de Direcciones**: Integración total con **Google Maps Autocomplete** para una selección de direcciones rápida y sin errores.
- **Geocodificación de Precisión**: Los puntos de origen y destino se guardan con coordenadas exactas (`lat`/`lng`) para evitar ambigüedades.
- **Ruta Circular Exacta**: El sistema calcula automáticamente el costo basándose en el recorrido total: `Base → Origen → Destino → Base`.
- **Precios en Tiempo Real**: Métricas de distancia y duración obtenidas mediante **Google Maps Distance Matrix API**.

### 2. **Panel de Administración Pro**
- **Gestión de Solicitudes**: Vista estilo Kanban para administrar pedidos Pendientes, Confirmados e Históricos.
- **Calendario Interactivo**: Resumen visual de todos los fletes confirmados y programados.
- **Control de Agenda**: Posibilidad de bloquear/habilitar fechas y horarios específicos directamente desde el panel.
- **Seguridad Robusta**: Login administrativo con protección contra fuerza bruta y sesiones seguras.

### 3. **Notificaciones Automatizadas**
- **WhatsApp Directo**: Uso de UltraMsg API para enviar alertas instantáneas a Javier con cada nuevo presupuesto o confirmación.
- **Mapas de un clic**: Los mensajes de WhatsApp incluyen enlaces dinámicos a Google Maps con las coordenadas exactas de la carga y descarga.

### 4. **Interfaz de Usuario de Alta Gama**
- **Diseño Glassmorphism**: Estética moderna con transparencias, gradientes y animaciones fluidas.
- **Single Page Application (SPA)**: Navegación instantánea gracias a un sistema de ruteo personalizado en JavaScript vanila.
- **Totalmente Responsive**: Optimizado para que el cliente pida su flete desde el celular o la computadora con la misma facilidad.

## 🛠️ Stack Tecnológico

- **Backend**: Python (FastAPI), Pydantic, Uvicorn.
- **Base de Datos**: MongoDB (Atlas) para almacenamiento flexible de documentos.
- **Frontend**: HTML5 Semántico, CSS3 Personalizado, JavaScript (ES6+).
- **Servicios Externos**: Google Maps (Places, Geocoding, Distance Matrix), UltraMsg (WhatsApp).
- **Deployment**: Configuración lista para Render (`render.yaml`).

## 🚀 Instalación y Configuración

### Requisitos Previos
- Python 3.10+
- Instancia de MongoDB (Local o Atlas).
- Claves de API de Google Maps con facturación habilitada.

### Pasos
1. **Clonar y entrar**:
   ```bash
   git clone https://github.com/sanwortley/Fletes_Exus.git
   cd Fletes_Exus
   ```
2. **Entorno Virtual**:
   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate | Mac/Linux: source .venv/bin/activate
   ```
3. **Dependencias**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Variables de Entorno**:
   Copia `.env.example` a `.env` y carga tus claves:
   - `GOOGLE_MAPS_API_KEY`: Tu clave de Google Cloud.
   - `MONGO_URI`: Tu conexión a MongoDB Atlas.
   - Otros costos operativos (Nafta, Hora Chofer, Peajes).

5. **Lanzar**:
   ```bash
   uvicorn backend.backend:app --reload
   ```

## 📸 Nota de Portafolio
Este proyecto demuestra la capacidad de integrar servicios complejos de terceros (Google Maps API) con lógica de negocio personalizada, priorizando siempre la simplicidad para el usuario final y la robustez para el administrador.

## 📄 Licencia
Este proyecto es de código abierto bajo la Licencia MIT.
