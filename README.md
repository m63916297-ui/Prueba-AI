# Agente Autónomo de Análisis y Síntesis de Documentación Técnica

## Descripción del Proyecto

Este proyecto implementa un agente de IA autónomo capaz de procesar documentación técnica desde URLs, entenderla y responder preguntas complejas sobre ella. El sistema utiliza LangGraph para orquestar el flujo de trabajo y proporciona una API RESTful para la interacción.

## Arquitectura de la Solución

### Componentes Principales

1. **API RESTful (FastAPI)**: Interfaz principal para interactuar con el agente
2. **LangGraph Workflow**: Orquesta el flujo de procesamiento y respuesta
3. **Base de Datos Vectorial (ChromaDB)**: Almacena embeddings de la documentación
4. **Base de Datos SQL (SQLite)**: Persiste conversaciones y estados
5. **Web Scraping**: Extrae contenido de URLs de documentación
6. **RAG Pipeline**: Recuperación y generación de respuestas

### Diagrama de Arquitectura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Cliente       │    │   FastAPI       │    │   LangGraph     │
│   (Frontend)    │◄──►│   (API REST)    │◄──►│   (Workflow)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   SQLite DB     │    │   ChromaDB      │
                       │   (Conversations│    │   (Embeddings)  │
                       │    & States)    │    └─────────────────┘
                       └─────────────────┘
```

### Flujo de LangGraph

```
Input Node → Intent Analysis → Conditional Router
                                    │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
            RAG Node         Code Analysis    Clarification
                    │                │                │
                    └────────────────┼────────────────┘
                                     │
                                     ▼
                            Response Generation
                                     │
                                     ▼
                            Code Formatting
                                     │
                                     ▼
                              Memory Node
```

## Decisiones Técnicas

### Framework Backend: FastAPI
- **Rendimiento**: Alto rendimiento con async/await
- **Documentación automática**: Swagger/OpenAPI integrado
- **Validación**: Pydantic para validación de datos
- **Facilidad de desarrollo**: Sintaxis moderna y intuitiva

### Base de Datos: SQLite + ChromaDB
- **SQLite**: Para conversaciones y estados (simplicidad y portabilidad)
- **ChromaDB**: Para embeddings vectoriales (fácil integración con Python)

### Modelos de IA
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (equilibrio entre velocidad y calidad)
- **LLM**: OpenAI GPT-4 (alta calidad de respuestas)

### Web Scraping: BeautifulSoup + Requests
- **Robustez**: Manejo de diferentes estructuras HTML
- **Limpieza**: Extracción inteligente de contenido relevante

## Instalación y Configuración

### Prerrequisitos
- Python 3.9+
- pip
- Git

### Pasos de Instalación

1. **Clonar el repositorio**
```bash
git clone <repository-url>
cd technical-docs-agent
```

2. **Crear entorno virtual**
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno**
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

5. **Inicializar base de datos**
```bash
python scripts/init_db.py
```

6. **Ejecutar el servidor**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Variables de Entorno

```env
# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Base de datos
DATABASE_URL=sqlite:///./technical_agent.db

# ChromaDB
CHROMA_PERSIST_DIRECTORY=./chroma_db

# Configuración del servidor
HOST=0.0.0.0
PORT=8000
```

## Uso de la API

### 1. Procesar Documentación

```bash
curl -X POST "http://localhost:8000/api/v1/process-documentation" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://docs.python.org/3/library/requests.html",
    "chat_id": "chat_123"
  }'
```

**Respuesta:**
```json
{
  "chat_id": "chat_123",
  "status": "processing",
  "message": "Documentation processing started"
}
```

### 2. Verificar Estado de Procesamiento

```bash
curl "http://localhost:8000/api/v1/processing-status/chat_123"
```

**Respuesta:**
```json
{
  "chat_id": "chat_123",
  "status": "completed",
  "progress": 100
}
```

### 3. Hacer Pregunta

```bash
curl -X POST "http://localhost:8000/api/v1/chat/chat_123" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "¿Cómo hago una petición GET con requests?"
  }'
```

**Respuesta:**
```json
{
  "chat_id": "chat_123",
  "response": "Para hacer una petición GET con requests...",
  "sources": ["https://docs.python.org/3/library/requests.html#requests.get"]
}
```

### 4. Obtener Historial

```bash
curl "http://localhost:8000/api/v1/chat-history/chat_123"
```

**Respuesta:**
```json
{
  "chat_id": "chat_123",
  "messages": [
    {
      "role": "user",
      "content": "¿Cómo hago una petición GET con requests?",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "role": "assistant",
      "content": "Para hacer una petición GET...",
      "timestamp": "2024-01-15T10:30:05Z"
    }
  ]
}
```

## Estructura del Proyecto

```
technical-docs-agent/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app
│   ├── config.py              # Configuración
│   ├── models/                # Modelos Pydantic
│   │   ├── __init__.py
│   │   ├── api.py
│   │   └── database.py
│   ├── services/              # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── document_processor.py
│   │   ├── chat_service.py
│   │   └── vector_store.py
│   ├── graph/                 # LangGraph workflows
│   │   ├── __init__.py
│   │   ├── agent_graph.py
│   │   └── nodes.py
│   └── database/              # Base de datos
│       ├── __init__.py
│       ├── models.py
│       └── database.py
├── scripts/
│   └── init_db.py
├── tests/
│   └── test_api.py
├── requirements.txt
├── .env.example
└── README.md
```

## Características Avanzadas

### Segmentación Inteligente
- División por secciones HTML
- Preservación de contexto semántico
- Manejo especial de bloques de código

### Análisis de Intención
- Clasificación automática de preguntas
- Enrutamiento inteligente a nodos especializados
- Detección de preguntas de seguimiento

### Memoria Conversacional
- Mantenimiento de contexto histórico
- Respuestas coherentes en conversaciones largas
- Referencias a mensajes anteriores

## Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles. 