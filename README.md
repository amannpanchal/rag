# Sagefold

<p align="center">
  <img src="public/sagefold-mark.svg" alt="Sagefold mark" width="88" />
</p>

<p align="center"><strong>A private workspace for asking questions across your documents.</strong></p>

Sagefold is a self-hostable document Q&A application. Upload files, let the ingestion pipeline extract and index their contents, and ask questions with source references. Accounts, documents, and conversations are scoped to their owner.

## Features

- Email and password sign-in with automatic account creation on first sign-in.
- Secure, server-managed sessions using HttpOnly cookies.
- User-scoped document listing, preview, deletion, and retrieval.
- Retrieval-augmented chat backed by PostgreSQL and Qdrant.
- Conversation history, streaming responses, and source citations.
- Responsive web interface with light and dark color tokens.

## Technology

- **Web:** Next.js, React, TypeScript, Tailwind CSS
- **API:** FastAPI, SQLAlchemy, Alembic
- **Data:** PostgreSQL and Qdrant
- **Models:** Google Gemini API for generation and embeddings

## Requirements

- Node.js 20 or newer and npm
- Docker Desktop with Docker Compose
- A Google AI Studio API key for Gemini

## Run locally

### 1. Configure the backend

```powershell
Copy-Item backend/.env.example backend/.env
```

Set `GOOGLE_API_KEY` and `POSTGRES_PASSWORD` in `backend/.env`. Replace the example database password with a strong local value. Keep `.env` files private and never commit real credentials.

### 2. Start database, vector store, and API

```powershell
cd backend
docker compose up -d postgres qdrant
```

Apply the database migrations and start the API:

```powershell
docker compose run --rm backend alembic upgrade head
docker compose up --build backend
```

The API is available at `http://localhost:8000`. In development, API documentation is available at `http://localhost:8000/docs`.

### 3. Start the web app

In a second terminal, from the repository root:

```powershell
npm install
Copy-Item .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. The Next.js development server proxies API calls to `http://localhost:8000`; set `BACKEND_URL` in `.env.local` if the API runs elsewhere, then restart Next.js.

## Authentication and account policy

`POST /api/v1/auth` accepts `{ "email": "you@example.com", "password": "at-least-8-characters" }`. It signs in an existing account or creates a new account for an unused email. An existing account with an incorrect password is rejected. There is no password reset or recovery flow; a lost password cannot be recovered.

The API sets an HttpOnly session cookie. Browser JavaScript does not store session credentials in local storage. Protected API routes derive the user identity from the session and enforce ownership on the server.

## Data isolation

Document ownership is stored in PostgreSQL and included in Qdrant payloads. Retrieval applies the authenticated owner's filter in Qdrant, then checks document ownership before returning context and citations. Conversations are also owner-scoped. Legacy records without a known owner stay inaccessible until an administrator assigns them deliberately.

The application currently stores extracted text and vectors; it does not retain source uploads for original-file downloads.

## Configuration

Backend settings are documented in [`backend/.env.example`](backend/.env.example). The root [`.env.example`](.env.example) configures the Next.js API proxy. Important backend values include:

| Variable | Purpose |
| --- | --- |
| `GOOGLE_API_KEY` | Gemini API credential |
| `POSTGRES_PASSWORD` | Local PostgreSQL password |
| `QDRANT_HOST` / `QDRANT_PORT` | Qdrant connection |
| `SESSION_TTL_SECONDS` | Session lifetime |
| `LOGIN_RATE_LIMIT_ATTEMPTS` | Login attempt limit per client window |
| `CORS_ORIGINS` | Allowed browser origins |

## Checks

```powershell
npm run lint
npm run build
```

Focused backend authentication and isolation tests:

```powershell
cd backend
.\venv\Scripts\python.exe -m unittest tests.test_user_auth_isolation
```

## License and project history

Sagefold is a rebranded and modified distribution of an existing MIT-licensed codebase. The original MIT license and copyright notice are preserved in [`LICENSE`](LICENSE), as required by that license. New branding assets in this repository were created for Sagefold. Review the license terms before redistributing the project.

## Contributing

Issues and pull requests are welcome. Do not include API keys, session cookies, private documents, or database dumps in issues or commits.