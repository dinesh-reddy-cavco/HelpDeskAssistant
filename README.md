# Cavco Intelligent Help Desk Chatbot

AI-assisted first line of support for IT help desk operations.

## Phase 1: Foundation & Safe First Demo

This phase includes:
- Basic chatbot interface
- Azure OpenAI integration
- Ability to answer common generic IT questions
- Safe behavior (refuses to guess)
- Logging of questions and outcomes

## Project Structure

```
HelpDeskAssistant/
├── backend/
│   └── app/
│       ├── __init__.py
│       ├── main.py              # FastAPI application
│       ├── config.py            # Configuration management
│       ├── models.py            # Data models
│       ├── services/
│       │   ├── __init__.py
│       │   ├── openai_service.py    # Azure OpenAI integration
│       │   ├── chat_service.py      # Chat logic
│       │   └── logging_service.py   # Conversation logging
│       └── database/
│           ├── __init__.py
│           ├── db.py            # Database connection
│           └── models.py        # Database models
├── frontend/
│   ├── index.html               # Chat UI
│   ├── styles.css               # Styling
│   └── app.js                   # Frontend logic
├── env.example                  # Environment variables template
├── requirements.txt             # Python dependencies
├── start_backend.bat            # Windows startup script
├── start_backend.sh             # Linux/Mac startup script
└── README.md
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `env.example` to `.env` in the project root and fill in your Azure OpenAI credentials:

**Windows:**
```bash
copy env.example .env
```

**Linux/Mac:**
```bash
cp env.example .env
```

Edit `.env` with your Azure OpenAI credentials:
- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint URL
- `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key
- `AZURE_OPENAI_DEPLOYMENT_NAME`: Your deployment name (e.g., "gpt-4" or "gpt-35-turbo")
- `AZURE_OPENAI_API_VERSION`: API version (default: "2024-02-15-preview")

### 3. Run the Backend

**Option 1: Using the startup script**

**Windows:**
```bash
start_backend.bat
```

**Linux/Mac:**
```bash
chmod +x start_backend.sh
./start_backend.sh
```

**Option 2: Manual start**
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will start on `http://localhost:8000`

### 4. Open the Frontend

**Option 1: Direct file open**
Simply open `frontend/index.html` in your web browser (double-click the file).

**Option 2: Using a local server (recommended)**
```bash
cd frontend
python -m http.server 8080
```

Then navigate to `http://localhost:8080` in your browser.

**Note:** The frontend is configured to connect to `http://localhost:8000` by default. If you change the backend port, update `API_BASE_URL` in `frontend/app.js`.

## API Endpoints

- `GET /` - Root endpoint with API information
- `GET /api/health` - Health check endpoint
- `POST /api/chat` - Send a chat message and get a response
  - Request body: `{"message": "your question", "conversation_id": "optional-id", "history": []}`
  - Response: `{"response": "assistant reply", "conversation_id": "uuid", "confidence": "high", "source": "generic", "requires_escalation": false}`

## Features (Phase 1)

✅ **Basic Chat Interface**
- Clean, modern UI with responsive design
- Real-time conversation flow
- Message history tracking

✅ **Azure OpenAI Integration**
- Direct integration with Azure OpenAI
- Configurable system prompts for safe behavior
- Conversation context management

✅ **Conversation Logging**
- All conversations stored in SQLite database
- Tracks user messages, assistant responses, confidence, and escalation flags
- Database auto-initializes on first run

✅ **Error Handling**
- Graceful error handling and user-friendly error messages
- API health checks
- Logging for debugging

## Development Notes

- The chatbot is configured to be safe and conservative in Phase 1
- All conversations are logged to a SQLite database (`chatbot.db` in the backend directory)
- The system will suggest escalation when uncertain
- CORS is enabled for all origins in development (restrict in production)


## Next Steps (Phase 2 & 3)

- **Phase 2**: Integrate Confluence documentation and ticket history (RAG)
- **Phase 3**: Smart ticket creation with ServiceDesk Plus integration
- **Future**: Entra ID authentication, production RAG improvements

---

## ⚠️ Critical TODOs & Deployment Considerations

- **SQLite is used by default for conversation logging.**
  - The backend creates a local `chatbot.db` SQLite file at startup (see `backend/app/config.py`).
  - **For production, replace SQLite with a managed database** (e.g., Azure SQL, PostgreSQL, MySQL) by setting the `DATABASE_URL` in your `.env` file and updating dependencies.
  - SQLite is not recommended for concurrent/multi-user production workloads.


- **Environment variables**: Never commit secrets or production credentials. Use `.env` for local dev, and secure secret management in production.

- **CORS is open to all origins** for development. Restrict `allow_origins` in `main.py` before deploying to production.

- **Logging**: Logs are written to the `logs/` directory. Ensure log rotation and secure log storage in production. consider external log storage. 

- **API keys and credentials**: Rotate regularly and use secure storage (Azure Key Vault, AWS Secrets Manager, etc.).

- **Frontend API URL**: If deploying backend/frontend separately, update `API_BASE_URL` in `frontend/app.js`. Using localhost now

- **Security**: No authentication is enforced in Phase 1. Add authentication (e.g., Entra ID, OAuth) before production use.

- **Error handling**: The backend logs errors but may expose details in API responses. Harden error handling for production.

- **Scalability**: The current setup is for demo/dev. For production, use a WSGI/ASGI server (e.g., Gunicorn, Uvicorn with workers) behind a reverse proxy (e.g., Nginx, Azure App Service).
