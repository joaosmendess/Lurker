# Lurker

Ferramenta pessoal de busca de emprego. O Lurker coleta vagas de várias fontes,
dá a cada uma uma **nota de 0 a 100** contra o meu currículo usando uma IA de
texto gratuita, ajusta o currículo para a vaga sem inventar nada e acompanha as
candidaturas num kanban.

Roda localmente: backend em Python (FastAPI + SQLite) e frontend em React.

## O que ele faz

- **Coleta vagas** de:
  - Gupy;
  - Remotive;
  - repositórios de vagas da comunidade no GitHub (backend-br, frontendbr…);
  - páginas de vagas de empresas no Greenhouse e no Lever.
- **Pré-filtra** pelo meu foco: modalidade (remoto, híbrido, presencial),
  cidades aceitas e palavras que excluem a vaga (estágio, staff…).
- **Dá nota a cada vaga** com a IA, com:
  - o porquê da nota;
  - o que eu tenho e o que falta;
  - alertas (nível sênior, presencial em outra cidade, inglês fluente obrigatório);
  - um pitch pronto para copiar.

  A lista "Para triar" vem ordenada pela nota.
- **Ajusta o currículo para a vaga** pensando em como sistemas de recrutamento
  (ATS, como Gupy, Greenhouse e Lever) leem o texto:
  - reescreve o resumo e reordena as habilidades;
  - copia as experiências **exatamente** como estão;
  - uma verificação em código, que não depende da IA, aponta qualquer data
    alterada, número ou termo inventado, ou habilidade removida.
- **Triagem rápida pelo teclado:** `J`/`K` navegam, `I` marca interesse, `X`
  descarta e `O` abre a vaga. Toda triagem pode ser desfeita.
- **Kanban das candidaturas:**
  - colunas Interesse → Aplicada → Em processo → Entrevista → Oferta → Recusada;
  - arrastar e soltar, também pelo teclado;
  - notas e histórico em cada card;
  - aviso quando uma candidatura fica parada há mais de 7 dias.
- **Telas de configuração:** "Foco" (perfil, currículo e preferências) e
  "Empresas" (cole o link da página de vagas para monitorar uma empresa).
- **Temas claro e escuro.** A interface é em português e responsiva.

## Limites (de propósito)

- **Não** automatiza login nem candidaturas em Gupy, LinkedIn, Greenhouse ou
  qualquer site que proíba automação. Nesses, o Lurker prepara o material e a
  pessoa clica em aplicar.
- **Não** faz scraping de páginas que exigem login, e respeita os limites de
  cada fonte (a Remotive aceita cerca de 4 requisições por dia).
- A IA nunca recebe ordem para inventar experiência. O que ela escreve "sobre
  mim" (currículo ajustado e pitch) passa por verificação automática.
- Chaves ficam só no `backend/.env`, que está fora do git.

## Requisitos

- Python 3.12+
- Node 22+
- Uma chave de IA gratuita (opcional, para a nota e o currículo ajustado): a
  [Groq](https://console.groq.com), em **API Keys**, não pede cartão.

## Rodando o backend

Comandos dentro de `backend/` (Windows):

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # depois preencha o .env

uvicorn app.main:app --reload   # API em http://localhost:8000/docs
```

### Configurando a IA

No `backend/.env`:

```bash
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=sua_chave
LLM_MODEL=openai/gpt-oss-120b
LLM_REASONING_EFFORT=low
```

Para ver os modelos que a sua chave oferece, rode `python -m app.llm`.

A integração usa o formato "compatível com OpenAI". Trocar de fornecedor
(Gemini, OpenRouter, Mistral, Ollama) é só mudar essas linhas.

Sobre o plano gratuito da Groq:
- os limites são de **8.000 tokens por minuto** e 1.000 pedidos por dia;
- por isso as notas são dadas em lotes de 60 (botão "Analisar vagas"), e cada
  lote espera a cota sozinho quando ela enche.

### Comandos úteis

```bash
python -m app.collect                 # coleta as vagas de todas as fontes
python -m app.scoring --limit 20      # dá nota às próximas 20 vagas pendentes
python -m app.companies add https://job-boards.greenhouse.io/<empresa> "Nome"
python -m app.filters                 # quantas vagas o pré-filtro deixa passar
```

O perfil (currículo e preferências) é editado na tela **Foco**. Para começar a
partir de um arquivo, copie o `profile.example.toml` para `profile.toml` (que
fica fora do git), preencha e rode `python -m app.profile import`.

## Rodando o frontend

Com o backend rodando, dentro de `frontend/`:

```bash
npm install
npm run dev                     # http://localhost:5173
```

## Testes e qualidade

```bash
# backend/
pytest                          # nenhum teste chama sites reais nem a IA real
ruff check . && ruff format --check .

# frontend/
npm test
npm run lint
npm run build
```

## Stack

- **Backend:** Python 3.13, FastAPI, SQLModel/SQLite, httpx, pydantic-settings,
  pytest e ruff.
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS 4, TanStack Query,
  React Router, dnd-kit e Vitest.
- **IA:** qualquer API de chat compatível com OpenAI (padrão: Groq gratuita).

## Próximos passos

- Envio do currículo por e-mail, com aprovação de cada envio, nas vagas que
  pedem currículo por e-mail.
- Coleta e análise automáticas todo dia útil, e um e-mail com as melhores vagas
  novas.
- Fontes internacionais de vagas remotas (opcional).

As decisões de projeto e as regras de trabalho estão no [CLAUDE.md](CLAUDE.md);
a pesquisa de interface, em [docs/ui-research.md](docs/ui-research.md).
