# Lurker

Ferramenta pessoal que busca vagas de emprego automaticamente em várias fontes,
avalia o encaixe de cada vaga com o meu currículo usando a API do Claude e
organiza as minhas candidaturas num kanban.

Objetivo final: eu abro o Lurker (ou o e-mail diário), vejo as melhores vagas
do dia já analisadas, com texto pronto para a candidatura, aplico com poucos
cliques e acompanho tudo num kanban.

---

## Sobre mim e como trabalhar comigo

- Sou dev full stack com experiência em C#/.NET, Node.js, React e SQL Server.
- Estou **aprendendo Python** com este projeto. Eu aprendo vendo: pode escrever
  o código, mas me ensine enquanto faz.
- Responda sempre em **português**. Código, nomes de variáveis, funções,
  tabelas e commits em **inglês**.

### Fluxo de cada tarefa

1. **Plano:** antes de mexer em arquivos, explique em poucas linhas o que vai
   fazer e por quê.
2. **Execução:** escreva o código em passos pequenos, um arquivo ou conceito
   por vez.
3. **Explicação:** depois de cada passo, explique o que foi feito. Quando
   aparecer algo novo de Python (decorators, context managers, list
   comprehensions, async, type hints, dataclasses, generators etc.), explique
   o conceito e compare com o equivalente em C# ou JavaScript.
4. **Validação:** rode o código ou os testes e mostre que funciona.
5. **Resumo:** ao final, liste em 3 a 5 tópicos "o que você aprendeu de Python
   nesta tarefa".

### Estilo de código

- Código simples e legível > código "esperto". Sem one-liners obscuros.
- Comentários explicam o **porquê**, não o óbvio. Em trechos com recurso novo
  de Python, um comentário curto explicando o recurso é bem-vindo.
- Type hints em tudo (parâmetros, retornos, atributos).
- Funções pequenas, com uma responsabilidade cada.
- Se houver duas formas de fazer, escolha a mais idiomática em Python e diga
  qual seria a alternativa.

---

## Stack

### Backend
- Python 3.12+
- FastAPI (API) + Uvicorn (servidor)
- SQLModel (ORM sobre SQLAlchemy + Pydantic) com SQLite; preparado para Postgres
- httpx (requisições HTTP)
- pydantic-settings (configuração via `.env`)
- APScheduler (agendamento da coleta diária)
- anthropic (SDK oficial da API do Claude)
- Playwright (somente na fase 6, para sites sem API)
- pytest + respx (testes, mock de HTTP)
- ruff (lint e formatação)

### Frontend (fase 4)
- React + Vite + TypeScript
- Tailwind CSS
- TanStack Query (dados da API)
- dnd-kit (arrastar cards no kanban)

---

## Estrutura do projeto

```
lurker/
├── CLAUDE.md
├── README.md
├── .gitignore
├── backend/
│   ├── .env                  # nunca commitar
│   ├── .env.example
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # cria o app FastAPI e registra as rotas
│   │   ├── config.py         # Settings (pydantic-settings)
│   │   ├── db.py             # engine, sessão, init_db
│   │   ├── models.py         # tabelas SQLModel
│   │   ├── schemas.py        # modelos de entrada/saída da API
│   │   ├── collect.py        # orquestra a coleta (CLI: python -m app.collect)
│   │   ├── filters.py        # pré-filtro barato antes da IA
│   │   ├── scoring.py        # avaliação com o Claude
│   │   ├── scheduler.py      # jobs agendados
│   │   ├── notifier.py       # e-mail resumo
│   │   ├── routers/          # jobs.py, applications.py, profile.py
│   │   └── sources/          # uma fonte por arquivo
│   │       ├── __init__.py
│   │       ├── base.py       # contrato comum das fontes
│   │       ├── remotive.py
│   │       ├── gupy.py
│   │       ├── greenhouse.py
│   │       └── lever.py
│   └── tests/
└── frontend/                 # fase 4
```

---

## Modelo de dados

- **Job**: uma vaga coletada.
  `id` (str, ex.: `"gupy:123"`, PK), `source`, `title`, `company`, `url`,
  `location`, `remote` (bool | None, None = desconhecido), `description`
  (texto puro, sem HTML), `published_at`, `collected_at`.
- **JobAnalysis**: resultado da IA para uma vaga (1:1 com Job).
  `job_id` (FK), `score` (0–100), `summary`, `matches` (lista),
  `gaps` (lista), `red_flags` (lista), `pitch`, `model`, `analyzed_at`.
- **Application**: minha candidatura (1:1 com Job, criada quando eu marco interesse).
  `job_id` (FK), `status`, `notes`, `created_at`, `updated_at`.
  Status: `interested` → `applied` → `in_process` → `interview` → `offer` | `rejected`;
  além de `discarded` para vagas que eu descartei.
- **StatusChange**: histórico de movimentações do kanban.
  `application_id`, `from_status`, `to_status`, `changed_at`.
- **Profile**: um único registro com o meu currículo (texto) e as preferências:
  modalidades aceitas, cidades aceitas, senioridade, regime (CLT/PJ),
  pretensão salarial, palavras para excluir.
- **WatchedCompany**: empresas monitoradas em Greenhouse/Lever (`provider`, `slug`).

Listas (matches, gaps etc.) podem ser guardadas como JSON numa coluna.

---

## Fontes de vagas

Toda fonte segue o mesmo contrato (`sources/base.py`): uma função que retorna
`list[Job]` já normalizada. Regras:

- Uma fonte falhar **nunca** derruba a coleta inteira: capture a exceção, logue
  e siga para a próxima.
- `timeout` explícito em toda requisição httpx (30s).
- Remova HTML das descrições antes de salvar.
- IDs no formato `"<fonte>:<id original>"` (Greenhouse/Lever: `"<fonte>:<empresa>:<id>"`).
- Ao integrar uma fonte nova, primeiro faça uma requisição real e mostre o
  formato da resposta antes de escrever o mapeamento.

Endpoints:
- **Remotive:** `https://remotive.com/api/remote-jobs?category=software-dev`
  (API pública e documentada; ignora o filtro de categoria, poucas vagas,
  máx. ~4 requisições/dia).
- **Gupy:** `https://portal.gupy.io/api/job-search/jobs?jobName=<termo>&offset=0&limit=100`
  (endpoint usado pelo portal, **não é API oficial**; o antigo
  `portal.api.gupy.io` foi desativado em out/2026; trate mudanças de formato
  com cuidado). `workplaceType` indica remoto (`remote`/`hybrid`/`on-site`).
  `pagination.total` não é confiável: pagine até vir página incompleta.
  Termos de busca em `GUPY_SEARCH_TERMS`.
- **Greenhouse:** `https://boards-api.greenhouse.io/v1/boards/<slug>/jobs?content=true`
- **Lever:** `https://api.lever.co/v0/postings/<slug>?mode=json`

### Limites éticos e de termos de uso (obrigatório)
- **Não** automatizar login nem candidaturas em LinkedIn, Gupy, Indeed ou
  qualquer plataforma que proíba automação. Nessas, o Lurker só prepara o
  material e eu clico em aplicar.
- **Não** fazer scraping de páginas que exigem login.
- Respeitar `robots.txt` no scraping com Playwright e manter intervalo entre
  requisições.
- Envio automático por e-mail só para vagas que pedem currículo por e-mail,
  e sempre personalizado.

---

## Pontuação com IA (scoring.py)

- Modelo configurável via `.env` (`CLAUDE_MODEL`), padrão `claude-haiku-5-5`
  (barato e suficiente para essa tarefa).
- **Não filtrar por stack.** Quero vagas de qualquer stack; a IA avalia o fit
  pela minha experiência geral, senioridade, modalidade e requisitos.
- O pré-filtro (`filters.py`) roda **antes** da IA para economizar: descarta
  por título usando `Profile.excluded_title_words` (estágio, staff, principal,
  gerente etc.; júnior e sênior **não** são descartados, a IA avalia) e por
  modalidade conforme o Profile.
- A IA deve penalizar: presencial/híbrido fora das cidades aceitas, senioridade
  muito acima, inglês fluente/nativo obrigatório, requisitos centrais ausentes.
- Resposta **somente em JSON** validado com Pydantic. Se o JSON vier inválido,
  logue e pule a vaga (sem quebrar o lote).
- O `pitch` é escrito em primeira pessoa, 2 a 3 frases, e **nunca** inventa
  experiência que não está no currículo.
- Limite de vagas analisadas por execução configurável (`MAX_JOBS_TO_SCORE`)
  para controlar custo.
- Nunca reanalisar uma vaga que já tem JobAnalysis, salvo pedido explícito.

---

## Configuração (.env)

```
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-haiku-5-5
DATABASE_URL=sqlite:///lurker.db
MAX_JOBS_TO_SCORE=60
MIN_SCORE_TO_EMAIL=65
GMAIL_USER=
GMAIL_APP_PASSWORD=
EMAIL_TO=
COLLECT_CRON=0 7 * * 1-5
COLLECT_COOLDOWN_MINUTES=120
TIMEZONE=America/Maceio
FRONTEND_ORIGIN=http://localhost:5173
GUPY_SEARCH_TERMS=desenvolvedor,developer,programador,engenheiro de software,full stack,backend
```

Toda configuração passa por `app/config.py` (pydantic-settings). Nada de
`os.getenv` espalhado pelo código. Mantenha o `.env.example` sempre atualizado.

---

## Comandos

Sempre dentro de `backend/`, com o venv ativo.

```bash
# criar e ativar o ambiente (Windows)
python -m venv .venv
.venv\Scripts\activate

# instalar dependências
pip install -r requirements.txt

# coletar vagas manualmente
python -m app.collect

# empresas monitoradas (Greenhouse/Lever)
python -m app.companies list
python -m app.companies add greenhouse <slug> "<Nome>"
python -m app.companies remove greenhouse <slug>

# perfil (currículo + preferências): edite profile.toml (git-ignored) e importe
python -m app.profile import
python -m app.profile show

# subir a API (docs em http://localhost:8000/docs)
uvicorn app.main:app --reload

# testes
pytest

# lint e formatação
ruff check . --fix
ruff format .
```

Frontend, dentro de `frontend/` (o backend precisa estar rodando):

```bash
npm install
npm run dev     # http://localhost:5173 (porta fixa: o CORS da API só libera ela)
npm run build   # checa tipos e gera dist/
npm run lint
```

Design do frontend: seguir `docs/ui-research.md` (direção "Classificados", temas
claro/escuro). Só existem as cores do Lurker (`bg-paper`, `text-ink`,
`text-signal`...): a paleta padrão do Tailwind foi removida de propósito.

Ao adicionar uma dependência: instale, atualize o `requirements.txt` e
explique para que ela serve.

---

## Testes

- Toda fonte tem teste com resposta HTTP mockada (respx), cobrindo o caminho
  feliz e o caso de a API falhar.
- `filters.py` e o parsing do JSON da IA têm testes unitários.
- Nunca chamar a API real do Claude nem sites reais nos testes.
- Rode `pytest` e `ruff check` antes de considerar uma tarefa pronta.

---

## Git

- Commits pequenos, um por passo lógico, no padrão Conventional Commits
  (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
- Sugira a mensagem de commit ao final de cada tarefa; só commite se eu pedir.
- Nunca commitar `.env`, `*.db`, `.venv/`, `__pycache__/`, `node_modules/`.

---

## Segurança

- Chaves só no `.env`. Nunca em código, logs ou commits.
- Não logar o currículo inteiro nem o conteúdo completo das vagas; logar IDs e títulos.
- CORS da API liberado apenas para o frontend local (`http://localhost:5173`).

---

## Roteiro

Atualize os checkboxes ao concluir cada item.

### Fase 1 — Coleta
- [x] Estrutura do backend, venv, requirements, .gitignore
- [x] Config (pydantic-settings) e banco (SQLModel + SQLite)
- [x] Modelo `Job`
- [x] Fonte Remotive
- [x] Fonte Gupy
- [x] `collect.py` salvando sem duplicar
- [x] Testes das fontes

### Fase 2 — Mais fontes e IA
- [x] Fontes Greenhouse e Lever + `WatchedCompany`
- [x] `Profile` com currículo e preferências
- [x] Pré-filtro
- [ ] Pontuação com Claude + `JobAnalysis`

### Fase 3 — API
- [x] FastAPI com rotas de vagas (listar, filtrar, detalhar)
- [x] Rotas de candidaturas (criar, mover status, notas)
- [x] Rotas de perfil e empresas monitoradas
- [x] Botão "coletar agora" (endpoint que dispara a coleta)

### Fase 4 — UI
- [x] Setup React + Vite + Tailwind + TanStack Query
- [ ] Lista de vagas com nota, filtros e ações (interesse/descartar)
- [ ] Detalhe da vaga com análise e pitch (botão copiar)
- [ ] Kanban de candidaturas com arrastar e soltar
- [ ] Tela de perfil e empresas monitoradas

### Fase 5 — Automação
- [ ] Coleta diária com APScheduler
- [ ] E-mail resumo diário com as melhores vagas novas

### Fase 6 — Extras
- [ ] Banco de respostas reutilizáveis para formulários
- [ ] Métricas (candidaturas/semana, taxa de resposta por fonte)
- [ ] Lembrete de follow-up
- [ ] Fontes via Playwright
- [ ] Envio automático para vagas que pedem currículo por e-mail
- [ ] Preparação para entrevista gerada pela IA
- [ ] Deploy

---

## Regras gerais

- Trabalhe numa fase por vez, seguindo o roteiro. Não adiante fases sem eu pedir.
- Se algo no roteiro ou neste arquivo parecer errado ou desatualizado, avise
  e sugira a mudança em vez de ignorar.
- Se uma tarefa for grande, divida em passos e confirme o plano comigo antes.
- Quando eu pedir "explica isso", explique o trecho linha a linha.