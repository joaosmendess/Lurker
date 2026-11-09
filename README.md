# Lurker

Ferramenta pessoal que busca vagas de emprego em várias fontes, avalia o
encaixe de cada vaga com o meu currículo usando a API do Claude e organiza as
candidaturas num kanban.

## Rodando o backend

Requer Python 3.12+. Comandos dentro de `backend/` (Windows):

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # preencha as chaves

pytest                   # testes
ruff check .             # lint
uvicorn app.main:app --reload   # API em http://localhost:8000/docs
```

## Rodando o frontend

Requer Node 22+. Com o backend rodando, dentro de `frontend/`:

```bash
npm install
npm run dev              # http://localhost:5173
```
