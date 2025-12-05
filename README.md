# WhatsApp RAG Multimodal Chatbot

Chatbot inteligente que responde a mensajes de texto y audio en WhatsApp usando Retrieval-Augmented Generation (RAG) y la API oficial de WhatsApp Cloud (Meta), sin intermediarios como Twilio.

## 🏗️ Arquitectura

### Patrón de Diseño: Clean Architecture + Layered Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI (main.py)                     │
│                  (Application Layer)                     │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              Routers (app/routers/)                      │
│         (Presentation / API Layer)                       │
│  - Webhook verification (GET)                           │
│  - Message reception & orchestration (POST)             │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              Services (app/services/)                    │
│         (Business Logic / Domain Layer)                  │
│  ├─ RAGEngine: Document indexing & querying             │
│  ├─ AudioService: Whisper & TTS                         │
│  └─ WhatsAppClient: Graph API integration               │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│         Configuration (app/config.py)                    │
│    (Environment & Settings Management)                  │
│  - Pydantic Settings for validation                     │
│  - Singleton pattern for cached settings               │
└─────────────────────────────────────────────────────────┘
```

### Patrones de Diseño Implementados

#### 1. **Singleton Pattern** (RAGEngine)
```python
# app/services/rag_service.py
class RAGEngine:
    _instance: Optional["RAGEngine"] = None
    _lock: Lock = Lock()
    
    def __new__(cls) -> "RAGEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
```
- **Propósito**: Garantizar una única instancia de RAGEngine en toda la aplicación
- **Beneficio**: El índice de documentos se carga una sola vez en memoria, mejorando rendimiento
- **Thread-safe**: Usa `Lock` para evitar race conditions

#### 2. **Dependency Injection** (Settings)
```python
# app/config.py
@lru_cache
def get_settings() -> Settings:
    return Settings()
```
- **Propósito**: Inyectar configuración en servicios sin hardcodear valores
- **Beneficio**: Fácil testeo, cambio de configuración sin modificar código
- **LRU Cache**: Evita recrear el objeto Settings en cada llamada

#### 3. **Repository Pattern** (WhatsAppClient)
```python
# app/services/whatsapp_client.py
class WhatsAppClient:
    def download_media(self, media_id: str) -> bytes:
    def upload_media(self, file_path: Path | str) -> str:
    def send_message(self, to: str, text: str, media_id: Optional[str] = None) -> None:
```
- **Propósito**: Abstraer la lógica de acceso a la API de Meta
- **Beneficio**: Cambios en Graph API se hacen en un solo lugar
- **Reutilizable**: Fácil de mockear en tests

#### 4. **Service Layer Pattern**
- **RAGEngine**: Encapsula lógica de indexación y consulta
- **AudioService**: Encapsula interacción con OpenAI (Whisper + TTS)
- **WhatsAppClient**: Encapsula interacción con Graph API

#### 5. **Async/Await + Thread Pool**
```python
# app/routers/whatsapp.py
await asyncio.to_thread(RAG_ENGINE.query, text)
await asyncio.to_thread(WHATSAPP_CLIENT.send_message, user_id, rag_response)
```
- **Propósito**: No bloquear el event loop de FastAPI
- **Beneficio**: Manejo eficiente de múltiples solicitudes concurrentes

#### 6. **Factory Pattern** (FastAPI App)
```python
# main.py
def create_app() -> FastAPI:
    application = FastAPI()
    application.include_router(whatsapp_router)
    return application

app = create_app()
```
- **Propósito**: Centralizar creación y configuración de la aplicación
- **Beneficio**: Facilita testing y múltiples instancias de app

---

## 📋 Estructura de Carpetas

```
bot voz whatasapp api/
├── main.py                          # Entrypoint de la aplicación
├── requirements.txt                 # Dependencias del proyecto
├── .env                             # Variables de entorno (no incluir en git)
├── README.md                        # Este archivo
├── data/                            # Documentos para RAG (crear manualmente)
│   ├── documento1.pdf
│   ├── documento2.txt
│   └── ...
└── app/
    ├── __init__.py
    ├── config.py                    # Configuración centralizada
    ├── services/
    │   ├── __init__.py
    │   ├── rag_service.py           # Motor RAG con LlamaIndex
    │   ├── audio_service.py         # Whisper + TTS
    │   └── whatsapp_client.py       # Cliente Graph API
    └── routers/
        ├── __init__.py
        └── whatsapp.py              # Endpoints webhook
```

---

## 🔄 Flujo de Funcionamiento

### Flujo de Mensaje de Texto

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Usuario envía TEXTO en WhatsApp                          │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 2. Meta envía webhook POST a /webhook                       │
│    Body: { "entry": [{ "changes": [{ "value": {            │
│             "messages": [{ "type": "text", "text": {...} }] │
│           }}]}]}                                             │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 3. _extract_messages() parsea el JSON                       │
│    Retorna: [{"from": "34123456789", "type": "text",       │
│              "text": "¿Cuál es tu nombre?"}]               │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 4. handle_message() → _handle_text_flow()                   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 5. RAG_ENGINE.query(text)                                   │
│    - Busca en índice LlamaIndex                             │
│    - Si no hay índice: fallback a GPT-4o-mini               │
│    Retorna: "Mi nombre es ChatBot RAG"                      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 6. WHATSAPP_CLIENT.send_message(to, rag_response)           │
│    POST https://graph.facebook.com/v18.0/{PHONE_ID}/messages│
│    Body: { "messaging_product": "whatsapp",                 │
│             "to": "34123456789",                            │
│             "type": "text",                                 │
│             "text": { "body": "Mi nombre es ChatBot RAG" }} │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 7. Meta envía el mensaje al usuario                         │
└─────────────────────────────────────────────────────────────┘
```

### Flujo de Mensaje de Audio

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Usuario envía AUDIO en WhatsApp                          │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 2. Meta envía webhook POST a /webhook                       │
│    Body: { "entry": [{ "changes": [{ "value": {            │
│             "messages": [{ "type": "audio",                 │
│                           "audio": { "id": "media_123",     │
│                                      "mime_type": "..." }}] │
│           }}]}]}                                             │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 3. _extract_messages() parsea el JSON                       │
│    Retorna: [{"from": "34123456789", "type": "audio",      │
│              "audio_id": "media_123", "mime_type": "..."}]  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 4. handle_message() → _handle_audio_flow()                  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 5. WHATSAPP_CLIENT.download_media(audio_id)                 │
│    GET https://graph.facebook.com/v18.0/media_123           │
│    → Obtiene URL de descarga                                │
│    → Descarga binario con Bearer Token                      │
│    Retorna: bytes del audio                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 6. transcribe_audio(file_path)                              │
│    POST https://api.openai.com/v1/audio/transcriptions      │
│    Model: whisper-1                                         │
│    Retorna: "¿Cuál es tu nombre?"                           │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 7. RAG_ENGINE.query(transcript)                             │
│    Retorna: "Mi nombre es ChatBot RAG"                      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 8. generate_audio(rag_response, output_path)                │
│    POST https://api.openai.com/v1/audio/speech              │
│    Model: gpt-4o-mini-tts, Voice: alloy                     │
│    Guarda MP3 en disco                                      │
│    Retorna: Path al archivo                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 9. WHATSAPP_CLIENT.upload_media(audio_path)                 │
│    POST https://graph.facebook.com/v18.0/{PHONE_ID}/media   │
│    Multipart: file=audio.mp3                                │
│    Retorna: media_id (ej: "media_456")                      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 10. WHATSAPP_CLIENT.send_message(to, "", media_id)          │
│     POST https://graph.facebook.com/v18.0/{PHONE_ID}/messages│
│     Body: { "messaging_product": "whatsapp",                │
│              "to": "34123456789",                           │
│              "type": "audio",                               │
│              "audio": { "id": "media_456" }}                │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 11. Meta envía el audio al usuario                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Instalación y Configuración

### 1. Clonar/Descargar el Proyecto

```bash
cd "bot voz whatasapp api"
```

### 2. Crear Entorno Virtual

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno

Crear archivo `.env` en la raíz del proyecto:

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WHATSAPP_TOKEN=EAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PHONE_NUMBER_ID=1234567890123
VERIFY_TOKEN=tu_token_secreto_para_webhook
```

**Cómo obtener cada variable:**

- **OPENAI_API_KEY**: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **WHATSAPP_TOKEN**: [Meta Business Platform](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started) → App → WhatsApp → API Access
- **PHONE_NUMBER_ID**: Número de teléfono registrado en Meta (sin +)
- **VERIFY_TOKEN**: Cadena aleatoria que defines (ej: `abc123xyz789`)

### 5. Crear Directorio de Datos

```bash
mkdir data
```

Agregar documentos en formato `.txt`, `.pdf`, `.docx`, etc. para que RAG los indexe.

### 6. Ejecutar la Aplicación

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- `--reload`: Reinicia automáticamente al cambiar código
- `--host 0.0.0.0`: Accesible desde cualquier IP
- `--port 8000`: Puerto de escucha

### 7. Exponer Localmente (Desarrollo)

Para que Meta pueda alcanzar tu webhook en desarrollo, usa **ngrok**:

```bash
ngrok http 8000
```

Obtendrás una URL como: `https://abc123.ngrok.io`

### 8. Configurar Webhook en Meta

1. Ve a [Meta App Dashboard](https://developers.facebook.com/apps)
2. Selecciona tu app → WhatsApp → Configuration
3. En **Webhook URL**: `https://abc123.ngrok.io/webhook`
4. En **Verify Token**: el valor de `VERIFY_TOKEN` en `.env`
5. Subscribe a eventos: `messages`, `message_template_status_update`

---

## 📦 Dependencias Principales

| Paquete | Versión | Propósito |
|---------|---------|----------|
| `fastapi` | 0.115.0 | Framework web asincrónico |
| `uvicorn` | 0.30.5 | Servidor ASGI |
| `requests` | 2.32.3 | Llamadas HTTP a Graph API |
| `openai` | 1.51.0 | SDK oficial de OpenAI |
| `llama-index-core` | 0.11.11 | Motor RAG |
| `llama-index-llms-openai` | 0.2.3 | Integración LLM con OpenAI |
| `llama-index-embeddings-openai` | 0.2.4 | Embeddings con OpenAI |
| `pydantic-settings` | 2.6.1 | Gestión de configuración |

---

## 🔐 Seguridad

### Buenas Prácticas Implementadas

1. **Variables de Entorno**: Nunca hardcodear tokens o claves
2. **Validación de Webhook**: Verificación de `hub.verify_token`
3. **Bearer Token**: Autenticación con Graph API
4. **Timeout en Requests**: Evitar bloqueos indefinidos (30s)
5. **Manejo de Errores**: Try-catch con logging

### Recomendaciones Adicionales

- Usar **AWS Secrets Manager**, **HashiCorp Vault** o similar en producción
- Implementar **rate limiting** en FastAPI
- Agregar **autenticación** si expones otros endpoints
- Usar **HTTPS** obligatoriamente
- Validar y sanitizar inputs de usuarios

---

## 🧪 Testing

### Simular Webhook de Meta (cURL)

```bash
# Verificación (GET)
curl -X GET "http://localhost:8000/webhook?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=tu_token_secreto_para_webhook"

# Mensaje de texto (POST)
curl -X POST "http://localhost:8000/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "34123456789",
            "type": "text",
            "text": {"body": "Hola, ¿cómo estás?"}
          }]
        }
      }]
    }]
  }'

# Mensaje de audio (POST)
curl -X POST "http://localhost:8000/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "34123456789",
            "type": "audio",
            "audio": {
              "id": "media_123",
              "mime_type": "audio/ogg"
            }
          }]
        }
      }]
    }]
  }'
```

---

## 📊 Monitoreo y Logs

La aplicación registra eventos en consola con niveles:

- **INFO**: Operaciones normales
- **WARNING**: Datos faltantes (ej: directorio `./data` no existe)
- **ERROR**: Fallos en procesamiento
- **EXCEPTION**: Errores no capturados

Ejemplo de log:

```
INFO:app.routers.whatsapp:Processing text message from 34123456789
INFO:app.services.rag_service:Querying RAG engine with: "¿Cuál es tu nombre?"
INFO:app.services.whatsapp_client:Sending text message to 34123456789
```

---

## 🚨 Troubleshooting

### Error: "Missing required environment variables"

**Solución**: Verificar que `.env` exista y contenga todas las variables requeridas.

### Error: "Data directory ./data not found"

**Solución**: Crear directorio `data/` y agregar documentos. RAG funcionará con fallback a GPT-4o-mini.

### Error: "Media URL not found in response"

**Solución**: Verificar que `WHATSAPP_TOKEN` sea válido y tenga permisos para acceder a media.

### Error: "Failed to obtain media id from WhatsApp"

**Solución**: Verificar que el archivo MP3 sea válido y `PHONE_NUMBER_ID` sea correcto.

### Webhook no recibe mensajes

**Solución**:
1. Verificar que ngrok esté corriendo
2. Verificar que webhook URL en Meta sea correcta
3. Verificar que `VERIFY_TOKEN` coincida
4. Revisar logs de Meta en App Dashboard

---

## 📈 Escalabilidad Futura

### Mejoras Posibles

1. **Base de Datos**: PostgreSQL para almacenar conversaciones
2. **Caché**: Redis para cachear respuestas frecuentes
3. **Queue**: Celery + RabbitMQ para procesamiento asincrónico
4. **Monitoring**: Prometheus + Grafana para métricas
5. **CI/CD**: GitHub Actions para deploy automático
6. **Containerización**: Docker + Docker Compose
7. **Multi-tenant**: Soportar múltiples números de WhatsApp
8. **Analytics**: Dashboard de conversaciones y métricas

---

## 📝 Licencia

Proyecto de código abierto. Úsalo libremente.

---

## 👨‍💻 Autor

Desarrollado como chatbot RAG multimodal para WhatsApp usando arquitectura limpia.

---

## 📞 Soporte

Para problemas o preguntas:
1. Revisar logs de la aplicación
2. Consultar documentación de [Meta](https://developers.facebook.com/docs/whatsapp/cloud-api)
3. Consultar documentación de [OpenAI](https://platform.openai.com/docs)
4. Consultar documentación de [LlamaIndex](https://docs.llamaindex.ai)
