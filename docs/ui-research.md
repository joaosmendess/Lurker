# Lurker: pesquisa de UI/UX (base da Fase 4)

> Status: **aprovado em 2026-11-09**. Direção A ("Classificados"), temas claro e escuro, interface em português, desktop primeiro e responsivo (seção 10).

## 1. Contexto: para quem e para quê

**Usuário:** uma pessoa só (eu), dev full stack. Uso diário no desktop, com consultas eventuais no celular.

**O ritual que a interface precisa servir:**

1. **Triagem (todo dia, 5 a 10 min):** abrir, ver o que chegou desde a última visita e decidir rápido para cada vaga: *interesse*, *descartar* ou *ver depois*.
2. **Decisão (algumas vagas por dia):** ler a vaga, a análise da IA e o pitch, copiar o pitch e abrir o link para aplicar.
3. **Acompanhamento (algumas vezes por semana):** mover cards no kanban, anotar e lembrar quem está parado há muito tempo.
4. **Manutenção (raro):** perfil, empresas monitoradas, "coletar agora".

**Consequência de design:** é uma ferramenta de **trabalho repetitivo e rápido**, como um cliente de e-mail ou um gerenciador de tarefas, não uma vitrine. Velocidade, densidade legível e teclado valem mais que ilustrações, cards gordos e animações.

## 2. Referências e o que tirar de cada uma

| Referência | O que copiar (a ideia, não o visual) | O que **não** copiar |
|---|---|---|
| **Superhuman** (e-mail) | Triagem por teclado: `J/K` navegam, uma tecla decide e já pula para o próximo. Meta de "inbox zero" para as vagas do dia. | O tema escuro com gradientes de marketing. |
| **Linear** | Densidade legível (linhas de ~36px, texto 13 a 14px), bordas no lugar de sombras, paleta de comandos `Ctrl+K`, UI otimista (o card move na hora e a API confirma depois). | Virou o visual mais copiado do SaaS. Imitar o *look* (preto, roxo, brilho) é exatamente a "cara de IA". |
| **Attio** (CRM) | O mesmo dado visto como **lista** e como **quadro**. Um pipeline de vendas é estruturalmente igual a um pipeline de candidaturas. Painel lateral de detalhe sem sair da lista. | Excesso de colunas configuráveis, que não faz sentido para um usuário só. |
| **Huntr** (rastreador de vagas) | Kanban com todas as etapas visíveis de uma vez, que é o ponto forte citado nas reviews. | Cards grandes com logo da empresa: pouca informação por tela. As reviews também apontam falta de métricas de conversão. |
| **Teal** (rastreador de vagas) | Checagem de requisitos da vaga contra o currículo, que no Lurker vira `matches`/`gaps` da IA. | O fluxo guiado e lento. As reviews dizem que ele pesa para quem aplica em volume. |
| **GitHub Projects** | O kanban continua utilizável **sem arrastar**: dá para mudar o status por um menu no card. | — |
| **Things 3** | Calma: muito espaço útil, hierarquia por tipografia (não por caixas e cores), estados vazios que dizem o que fazer. | — |

## 3. Princípios

1. **Lista antes de card.** Uma vaga é um registro com 5 ou 6 campos: título, empresa, local/modalidade, fonte, data e nota. Isso pede **uma linha por vaga**, que dá para escanear na vertical, e não uma grade de cards. Cards só no kanban, onde a posição na coluna *é* a informação.
2. **Master-detail.** No desktop, a lista fica à esquerda e o detalhe à direita, sem trocar de página. No celular, a lista ocupa a tela, o detalhe abre em tela cheia e há botão de voltar.
3. **Teclado primeiro, mouse sempre funciona.** Toda ação tem atalho, mas também tem botão. Os atalhos ficam visíveis (`?` abre a lista deles).
4. **Arrastar nunca é a única forma.** No kanban, cada card tem um menu "Mover para…". Isso atende WCAG 2.1.1, celular e teclado. O arrastar com dnd-kit também precisa funcionar pelo teclado: Espaço pega, setas movem e Espaço solta.
5. **UI otimista + desfazer.** Descartar ou mover acontece na hora, com um aviso "Vaga descartada · Desfazer" por alguns segundos. Nada de diálogo "Tem certeza?" para ação reversível.
6. **Cor é informação, não decoração.** Uma cor de destaque só. As outras cores só aparecem para **significar** algo: nota da IA, status e "nova".
7. **Bordas, não sombras.** Sombra só em elementos que flutuam (menus, modais, toast).
8. **Tipografia faz a hierarquia.** Peso e tamanho no lugar de caixas coloridas e ícones decorativos.
9. **Estados vazios orientam.** "Nenhuma vaga nova desde ontem. Próxima coleta às 07:00 · Coletar agora", e não uma ilustração genérica.
10. **Rápido é parte do design.** Cache com TanStack Query, paginação e nada de spinners de tela inteira (skeleton só na primeira carga).

## 4. Checklist anti-"cara de IA"

Segundo os artigos levantados, o visual "gerado por IA" é a **média** dos templates: Inter, botão índigo (`bg-indigo-500`, o padrão histórico do Tailwind UI), hero centralizado e três cards arredondados. Para o Lurker:

- [ ] **Nada de** roxo/índigo, gradientes, brilho (*glow*), glassmorphism e emojis como ícones.
- [ ] **Nada de** Inter, Geist ou Space Grotesk, as fontes "padrão" de 2024 a 2026.
- [ ] **Nada de** cards com `rounded-2xl` + sombra grande + ícone colorido no canto.
- [ ] **Nada de** painel de métricas com "número grande + rótulo pequeno + seta verde" se a métrica não ajudar a decidir algo.
- [ ] **Sem** copiar o visual dos componentes do shadcn/ui. Se usar, só os primitivos sem estilo (Radix) e com os tokens próprios.
- [ ] **Texto** com verbos que dizem o que acontece ("Descartar vaga", "Mover para Entrevista", "Copiar pitch"), sem "Submit", "Oops!" ou "Algo deu errado 😢".
- [ ] **Tokens definidos antes** do primeiro componente: cor, fonte, raio, espaçamento e elevação. Os artigos concordam que o visual genérico aparece quando os padrões não são trocados logo no início.

E também evitar os três "estilos alternativos" que já viraram clichê de IA: (1) fundo creme + serifa + terracota; (2) preto + um único verde-ácido; (3) layout de jornal com linhas finas e zero arredondamento.

## 5. Telas

### 5.1 Vagas (tela principal: triagem)

```
Desktop (≥1024px)
┌───────────┬──────────────────────────────────┬─────────────────────────────┐
│ Lurker    │ Vagas            [Novas][Todas]  │ Desenvolvedor .NET Pleno    │
│           │ ⌕ Buscar…   Fonte▾ Modal.▾       │ Empresa X · Remoto · Gupy   │
│ Vagas  38 │──────────────────────────────────│ publicada há 2 dias         │
│ Kanban    │ 82 ●  Dev .NET Pleno     Emp X  2d│─────────────────────────────│
│ Empresas  │ 74    Full Stack React   Emp Y  3d│ Nota 82 · Por que encaixa   │
│ Perfil    │ 61    Backend Node       Emp Z  3d│ ✓ C#/.NET  ✓ SQL Server     │
│           │ —     Java Developer     Emp W  4d│ ✗ Kubernetes                │
│ ───────── │ …                                 │ Pitch          [Copiar]     │
│ Coleta    │                                   │ "Tenho 3 anos com .NET…"    │
│ hoje 07:02│                                   │ [Interesse I] [Descartar X] │
│ [Coletar] │                                   │ [Abrir vaga ↗]              │
└───────────┴──────────────────────────────────┴─────────────────────────────┘
 J/K navega · I interesse · X descarta · O abre a vaga · C copia o pitch
```

- **"Novas"** por padrão: vagas que passaram no pré-filtro e ainda não têm candidatura, ou seja, as que faltam triar. O contador na barra lateral funciona como um "inbox".
- **Ordem:** pela nota (quando a IA existir), senão pela data de publicação.
- **Celular:** só a lista. Tocar na vaga abre o detalhe em tela cheia, com as ações fixas no rodapé, ao alcance do polegar.

### 5.2 Kanban

```
Desktop
 Interesse (6)   Aplicada (9)    Em processo (3)  Entrevista (1)  Oferta  Encerradas ▸
 ┌────────────┐  ┌────────────┐  ┌────────────┐   ┌────────────┐
 │Dev .NET    │  │Full Stack  │  │Backend Node│   │React Dev   │
 │Emp X       │  │Emp Y       │  │Emp Z  ⏱ 12d│   │Emp W       │
 └────────────┘  └────────────┘  └────────────┘   └────────────┘
```

- **Colunas:** Interesse → Aplicada → Em processo → Entrevista → Oferta. **Recusada** e **Descartada** ficam juntas numa coluna "Encerradas", recolhida por padrão, para não poluir.
- **Tempo parado no estágio** (`⏱ 12d`): calculado a partir do `StatusChange`. Aparece só quando passa de um limite (por exemplo, 7 dias). É o lembrete de follow-up da Fase 6 nascendo como informação visual.
- **Celular:** uma coluna por vez, com abas no topo para trocar de etapa. Arrastar não é necessário: o menu "Mover para…" do card resolve.

### 5.3 Detalhe da candidatura
Painel lateral (desktop) ou tela cheia (celular) com: dados da vaga, notas (salvam sozinhas) e a **linha do tempo** do histórico de status.

### 5.4 Perfil e empresas
Formulários simples numa coluna. O currículo vai num `textarea` grande. Empresas aparecem numa tabela com interruptor de ativar/pausar.

## 6. Responsividade

| Largura | Layout |
|---|---|
| < 640px (celular) | Navegação inferior (Vagas, Kanban, Mais). Lista → detalhe em tela cheia. Kanban com uma coluna e abas. Ações de no mínimo 44px de altura. |
| 640 a 1023px (tablet) | Barra lateral recolhida em ícones. Lista + detalhe em painel deslizante. Kanban com rolagem horizontal. |
| ≥ 1024px | Três áreas: navegação, lista e detalhe. Kanban com todas as colunas visíveis. |

## 7. Acessibilidade (piso mínimo)
- Foco visível em tudo, com contraste AA (4.5:1 no texto).
- Kanban operável sem mouse (menu "Mover para…" + teclado no dnd-kit + anúncios `aria-live`).
- `prefers-reduced-motion` respeitado.
- Status nunca indicado **só** por cor: sempre com o texto do status junto.

## 8. Direções visuais (escolher uma)

### Direção A: "Classificados" (recomendada)
Vagas de emprego nasceram nos **classificados de jornal**. A ideia é trazer a *tipografia* desse mundo, sem imitar o layout de jornal (que é o clichê nº 3).

| Token | Claro | Escuro | Uso |
|---|---|---|---|
| `paper` | `#F7F8F6` | `#141816` | fundo (cinza frio, não creme; no escuro, grafite esverdeado, nunca preto puro) |
| `surface` | `#FFFFFF` | `#1B201E` | painéis, linha selecionada, menus |
| `ink` | `#1D2321` | `#E4E8E6` | texto principal |
| `graphite` | `#5F6A66` | `#9AA5A0` | texto secundário, metadados |
| `rule` | `#DCE1DE` | `#2A312E` | bordas e divisórias |
| `signal` | `#C2410C` | `#F0864A` | **única** cor de destaque: "nova", foco, ação principal |
| `fit-high` | `#15803D` | `#4ADE80` | nota alta (≥ 75) |
| `fit-mid` | `#B45309` | `#F5A524` | nota média (50 a 74) |
| `fit-low` | `#5C636E` | `#8B949E` | nota baixa (< 50) |

Contraste calculado (fórmula WCAG) contra `paper`. Todos passam no AA (≥ 4.5:1 para texto):

| Token | Claro | Escuro |
|---|---|---|
| `ink` | 15.0 | 14.5 |
| `graphite` | 5.3 | 7.1 |
| `signal` | 4.9 | 7.0 |
| `fit-high` | 4.7 | 10.3 |
| `fit-mid` | 4.7 | 8.8 |
| `fit-low` | 5.7 | 5.8 |

O cinza `#9CA3AF` da primeira versão dava 2.4:1 e foi trocado. Sobre `surface`, os valores do claro sobem um pouco e os do escuro caem cerca de 0.5, todos ainda acima de 4.5.

**Tema:** segue o sistema operacional por padrão (`prefers-color-scheme`), com um seletor Sistema / Claro / Escuro que fica salvo no navegador. Os tokens viram variáveis CSS, e trocar de tema é trocar um atributo `data-theme` no `<html>`, sem duplicar componentes.

- **Fontes:** *Schibsted Grotesk* (títulos; desenhada para um grupo de mídia de notícias) + *Atkinson Hyperlegible Next* (corpo; criada para legibilidade máxima) + *JetBrains Mono* (datas, IDs, nota).
- **Forma:** raio de 6px, bordas de 1px, sombra só em menus flutuantes.
- **Assinatura:** a **nota da IA como "carimbo"**, um número em mono, alinhado à esquerda de cada linha como um código de classificado. É o elemento que você bate o olho para decidir.

### Direção B: "Radar noturno"
"Lurker" é quem observa em silêncio. Tema **escuro por padrão**, mas sem o preto puro e o roxo do Linear: um **azul-petróleo profundo** (`#0F1D22`), texto `#E3EAE8` e destaque âmbar (`#F2A93B`), a cor de um sinal num radar. As mesmas fontes, com mais espaçamento. A assinatura seria um indicador discreto de "novas desde a última visita" pulsando uma vez ao abrir.

**Por que recomendo A:** o uso é diurno e de leitura longa (descrições de vaga). O tema claro cansa menos para ler, e o tema escuro pode existir como alternativa. B é mais "tela de hacker" e corre mais risco de cair no visual "SaaS escuro" genérico.

## 9. Ajustes no backend que a UI vai pedir
- `GET /jobs` precisa devolver o **status da candidatura** de cada vaga (ou `null`), para filtrar "Novas" (sem candidatura) e mostrar o selo.
- Filtro `?untriaged=true` (passou no pré-filtro e não tem candidatura).
- Na lista do kanban, os **dias desde a última mudança** de status.

## 10. Decisões tomadas
1. Direção visual: **A ("Classificados")**.
2. Tema: **claro e escuro**, seguindo o sistema, com seletor manual.
3. Idioma da interface: **português** (padrão assumido; não confirmado explicitamente).
4. Celular: **funciona bem** (desktop primeiro, responsivo), não "mobile first" (padrão assumido; não confirmado explicitamente).

## Fontes
- Linear, densidade e teclado: [The Linear Aesthetic, Decoded](https://www.buildmvpfast.com/blog/linear-aesthetic-tokens-density-keyboard-first-ux-2026), [Linear Design Breakdown](https://www.925studios.co/blog/linear-design-breakdown-saas-ui-2026), [Linear: guia de design (PT)](https://blakecrosley.com/pt-BR/guides/design/linear), [Linear teardown](https://michaelflanigan.pages.dev/blog/linear-teardown)
- Rastreadores de vagas: [Huntr vs Teal (Huntr)](https://huntr.co/blog/huntr-vs-teal), [Huntr review](https://scoutify.com/blog/huntr-review), [Teal vs Huntr 2026](https://cloudcolleague.com/blogs/job-hunting/teal-vs-huntr/), [Teal vs Huntr vs Simplify](https://bestjobsearchapps.com/articles/en/teal-vs-huntr-vs-simplify-pros-and-cons), [Teal vs Huntr vs Simplify vs Hppr](https://hppr-blog.vercel.app/p/teal-vs-huntr-vs-simplify-vs-hppr-ai)
- Kanban, arrastar e acessibilidade: [Drag and Drop Accessibility](https://www.continualengine.com/blog/drag-and-drop-accessibility/), [Draggable accessibility](https://frontendchecklist.io/rules/accessibility/draggable-accessibility), [WCAG 2.2 G219](https://www.w3.org/WAI/WCAG22/Techniques/general/G219), [Dragging movements](https://dev-accessibility.arbisoft.com/designer-guidelines/operable/dragging-movements), [Jira: bug de teclado no board](https://jira.atlassian.com/browse/JRASERVER-73305), [Padrão kanban](https://skillselion.com/skills/thedaviddias/ux-patterns-for-developers/kanban-board)
- Lista × tabela × cards: [Data table UI guide 2026](https://www.setproduct.com/blog/data-table-ui-design), [Cards vs rows](https://cdn.jsdelivr.net/npm/@exxatdesignux/ui@0.6.59/consumer-extras/patterns/card-vs-rows-pattern.md), [List view pattern](https://skills.sh/thedaviddias/ux-patterns-for-developers/list-view), [Pedido de "list view" real](https://feedback.recall.it/feature-requests/p/a-proper-list-view-to-easily-see-all-the-cards-on-the-page-in-a-condensed-format)
- Responsividade e master-detail: [Responsive design for business apps](https://thepropermotioncompany.pages.dev/blog/responsive-design-for-complex-business-applications/), [Mobile tables design](https://www.ramotion.com/blog/mobile-tables-design/), [Responsive tables (acessível)](https://www.digitalthriveai.com/en-us/resources/frontend-development/accessible-front-end-patterns-responsive-tables-part2/)
- "Cara de IA": [Why your AI keeps building the same purple gradient website](https://prg.sh/ramblings/Why-Your-AI-Keeps-Building-the-Same-Purple-Gradient-Website), [Blame Tailwind's indigo-500](https://dev.to/alanwest/why-every-ai-built-website-looks-the-same-blame-tailwinds-indigo-500-3h2p), [How to fix the AI-generated look](https://dev.to/alanwest/how-to-fix-the-ai-generated-look-in-your-frontend-1ahh), [AI design slop 2026](https://noqta.tn/en/blog/ai-design-slop-overused-ui-patterns-fix-2026), [Why AI design looks generic](https://www.superdesign.dev/blog/why-ai-design-looks-generic)
- Attio, Superhuman, Things 3 e GitHub Projects: observações de uso dos próprios produtos, sem artigo específico.
