"""Tailor my resume to one job with the text AI, without inventing or changing experience.

The AI may only rewrite the summary, reorder the skills and the sections, and use
the job's own words for things I already have. Experience is copied as is, and
check_preserved verifies that in code instead of trusting the model.
"""

import logging
import re
from collections import Counter

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session

from app.llm import LLMBadAnswerError, LLMConfig, LLMError, chat
from app.models import Job, TailoredResume, utc_now

MAX_JOB_CHARS = 12_000  # long descriptions are cut, so the prompt fits free-tier limits
ATTEMPTS = 2  # one retry when the model answers the wrong shape

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Você adapta currículos a uma vaga para que sistemas de recrutamento (ATS, como Gupy, \
Greenhouse e Lever) e recrutadores encontrem rápido o que a pessoa já tem.

Regras obrigatórias:
1. NUNCA invente nada: nenhuma experiência, empresa, cargo, data, tecnologia, \
certificação, número ou resultado que não esteja no currículo original.
2. Copie a experiência profissional EXATAMENTE como está: empresas, cargos, datas e cada \
linha de descrição, palavra por palavra e na mesma ordem. Copie também formação, cursos \
e idiomas sem alterar.
3. Você só pode mudar:
   a) o RESUMO: reescreva em 3 a 4 frases usando SOMENTE fatos e termos que já estão no \
currículo, destacando primeiro o que também aparece na vaga. É PROIBIDO trazer para o \
resumo termos da vaga que o currículo não tem (metodologias, cargos com quem trabalha, \
arquiteturas, ferramentas): se a vaga pede Scrum e o currículo não diz Scrum, não escreva \
Scrum nem "ágil";
   b) a seção HABILIDADES, que aparece UMA única vez: mantenha as linhas e os rótulos do \
original (ex.: "Backend: ..."), coloque primeiro as linhas mais ligadas à vaga e, dentro \
de cada linha, primeiro os itens que a vaga pede. Não crie uma segunda lista, não mova \
itens de uma linha para outra, não repita itens e não remova nenhuma linha nem item;
   c) a ordem das seções: RESUMO, HABILIDADES, EXPERIÊNCIA PROFISSIONAL, FORMAÇÃO e as \
demais do original.
4. Formato para ATS: texto puro, sem tabelas, colunas, emojis ou símbolos decorativos; \
títulos de seção em maiúsculas; itens de lista começando com "- "; nome e cidade no topo, \
como no original. Mantenha o idioma do currículo original.

Responda APENAS neste formato, com os três marcadores exatamente assim, sem nada antes \
nem depois e sem blocos de código:
===CURRICULO===
(o currículo completo adaptado, em texto puro)
===AJUSTES===
- (uma frase curta por ajuste que você fez)
===FALTANDO===
- (um item por requisito importante da vaga que NÃO aparece no currículo; só para a \
pessoa se preparar, não coloque no currículo)"""

# The markers the prompt asks for. ^...$ with MULTILINE: a whole line, anywhere in the text
SECTION_MARKER = re.compile(r"^=+\s*(CURRICULO|CURRÍCULO|AJUSTES|FALTANDO)\s*=+\s*$", re.MULTILINE)
LIST_ITEM = re.compile(r"^\s*(?:[-•*]|\d+[.)])\s*")


class TailoringAnswer(BaseModel):
    """The answer once parsed. Anything else is retried, then rejected."""

    resume: str = Field(min_length=50)
    changes: list[str] = []
    missing: list[str] = []


# Look-alike characters models like to emit, and their plain versions. ATS parsers may
# not match "Full‑Stack" (non-breaking hyphen) when a recruiter searches "Full-Stack".
LOOKALIKES = str.maketrans(
    {
        "‐": "-",  # hyphen
        "‑": "-",  # non-breaking hyphen
        "‒": "-",  # figure dash
        "­": "",  # soft hyphen (invisible)
        " ": " ",  # no-break space
        " ": " ",  # figure space
        " ": " ",  # narrow no-break space
        "​": "",  # zero-width space
    }
)


def plain_text(text: str) -> str:
    """Swap look-alike characters for the plain ones (str.translate: one pass, like a map)."""
    return text.translate(LOOKALIKES)


def parse_list(block: str) -> list[str]:
    """ "- a\\n- b" -> ["a", "b"]. "Nenhum" style answers become an empty list."""
    items = [LIST_ITEM.sub("", line).strip() for line in block.splitlines()]
    return [item for item in items if item and item.casefold() not in {"nenhum", "nenhuma", "-"}]


def parse_answer(text: str) -> TailoringAnswer:
    """Split the model's text at the ===MARKERS===. Raises LLMBadAnswerError if it can't."""
    # re.split with a capture group keeps the markers: ["", "CURRICULO", "...", "AJUSTES", ...]
    parts = SECTION_MARKER.split(text)
    sections: dict[str, str] = {}
    # zip(parts[1::2], parts[2::2]): (marker, text after it) pairs, like a pairwise loop
    for name, body in zip(parts[1::2], parts[2::2], strict=True):
        sections[name.replace("Í", "I")] = body.strip()

    try:
        return TailoringAnswer(
            resume=sections.get("CURRICULO", ""),
            changes=parse_list(sections.get("AJUSTES", "")),
            missing=parse_list(sections.get("FALTANDO", "")),
        )
    except ValidationError as error:
        raise LLMBadAnswerError("The answer has no ===CURRICULO=== section") from error


def build_user_prompt(resume: str, job: Job) -> str:
    description = job.description[:MAX_JOB_CHARS]
    return (
        f"VAGA: {job.title}\nEMPRESA: {job.company}\nLOCAL: {job.location or 'não informado'}\n\n"
        f"DESCRIÇÃO DA VAGA:\n{description}\n\n"
        f"CURRÍCULO ORIGINAL:\n{resume}"
    )


# --- Automatic check ----------------------------------------------------------------

YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
# Any number, with its thousands/decimal separator: "3", "10.000", "4,5"
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# Bullets the model may legitimately swap for "- " (ATS format)
LEADING_BULLET = re.compile(r"^[\s\-–—•*·▪●]+")


def normalize_line(line: str) -> str:
    """Ignore what the format rules allow to change: bullet, spacing and letter case."""
    without_bullet = LEADING_BULLET.sub("", line)
    return " ".join(without_bullet.split()).casefold()


# A word, keeping tech names whole: "C#", "C++", "Node.js", "Full-Stack", "CI/CD"
WORD = re.compile(r"[\w#+]+(?:[.\-/][\w#+]+)*")
SENTENCE_END = re.compile(r"(?<=[.!?;:])\s+")


def is_heading(line: str) -> bool:
    letters = [char for char in line if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters)


def new_terms(original: str, tailored: str) -> list[str]:
    """Capitalized words (tech, roles, methods) in the tailored text that the original lacks.

    Mid-sentence capitals are what an invented claim looks like: "Cloud Native",
    "Tech Leads", "QA". Sentence starts and headings are skipped, since those are
    capitalized anyway. Neighbouring flagged words are joined: ["Cloud Native"].
    """
    known_words = {word.casefold() for word in WORD.findall(original)}
    # "front-end" vs "frontend" is spelling, not a new claim: also compare without hyphens
    known_unhyphenated = {word.replace("-", "") for word in known_words}
    original_text = " ".join(original.split()).casefold()

    def is_new(word: str) -> bool:
        if "/" in word:
            # "AWS/Azure" is two known things side by side, unless "CI/CD" itself is known
            whole = word.casefold() in known_words
            return not whole and any(is_new(part) for part in word.split("/") if part)
        lowered = word.casefold()
        return lowered not in known_words and lowered.replace("-", "") not in known_unhyphenated

    phrases: list[str] = []

    for line in tailored.splitlines():
        if is_heading(line):
            continue
        for sentence in SENTENCE_END.split(line.strip()):
            # finditer (not findall): keeps each word's position, to see what's between them
            words = list(WORD.finditer(sentence))
            flagged = [False] * len(words)
            for index, match in enumerate(words):
                word = match.group()
                # Hyphenated words count too, even in lowercase: "cloud-native"
                if index == 0 or not (any(char.isupper() for char in word) or "-" in word):
                    continue
                if is_new(word):
                    flagged[index] = True
                previous = words[index - 1]
                # Two known words can still form a new term: "Cloud" + "Native"
                joined = sentence[previous.end() : match.start()].isspace()
                pair = f"{previous.group()} {word}".casefold()
                if (
                    index > 1
                    and joined
                    and previous.group()[0].isupper()
                    and pair not in original_text
                ):
                    flagged[index - 1] = flagged[index] = True

            # Group flagged words that are only separated by spaces into one phrase
            current: list[str] = []
            for index, match in enumerate(words):
                adjacent = index > 0 and sentence[words[index - 1].end() : match.start()].isspace()
                if flagged[index] and current and adjacent:
                    current.append(match.group())
                    continue
                if current:
                    phrases.append(" ".join(current))
                current = [match.group()] if flagged[index] else []
            if current:
                phrases.append(" ".join(current))
    return list(dict.fromkeys(phrases))  # dedupe, keeping order


def skill_items(text: str) -> list[str]:
    """Items of the HABILIDADES section: "Backend: .NET, Node.js" -> [".NET", "Node.js"]."""
    items: list[str] = []
    in_skills = False
    for line in text.splitlines():
        if is_heading(line):
            in_skills = normalize_line(line).startswith(("habilidades", "skills"))
            continue
        if in_skills and line.strip():
            values = line.split(":", 1)[-1]  # drop the "Backend:" label when there is one
            items += [item.strip(" -•.") for item in values.split(",") if item.strip(" -•.")]
    return items


def count_lines(text: str) -> Counter[str]:
    return Counter(normalized for line in text.splitlines() if (normalized := normalize_line(line)))


def check_invented(original: str, text: str) -> list[str]:
    """Numbers and capitalized/hyphenated terms in `text` that `original` doesn't have.

    Shared by the tailored resume and the job pitch: anything written "about me"
    may only use what my resume says.
    """
    warnings: list[str] = []
    original_numbers = set(NUMBER.findall(original))
    # sorted(set(...)): each invented number reported once, in order
    for number in sorted(set(NUMBER.findall(text)) - original_numbers):
        warnings.append(f"Apareceu um número que não está no seu currículo: {number}")
    terms = new_terms(original, text)
    if terms:
        warnings.append(f"Termos que não estão no seu currículo: {', '.join(terms)}")
    return warnings


def check_preserved(original: str, tailored: str) -> list[str]:
    """What looks changed or invented, in plain words for the screen (empty = all good).

    Five checks, none trusting the model:
    - lines with a year are the factual core (jobs, dates, degrees): each must come back;
    - no number may appear that isn't in the original ("5 anos", ".NET 8", "2019");
    - no line may be repeated unless it already was (a skills list written twice);
    - no capitalized term the original lacks ("Cloud Native", "Tech Leads", "QA");
    - every item of the original HABILIDADES section is still there.
    """
    tailored_counts = count_lines(tailored)
    tailored_text = normalize_line(tailored.replace("\n", " "))

    warnings: list[str] = []
    for line in original.splitlines():
        if not YEAR.search(line):
            continue
        normalized = normalize_line(line)
        # Accept it as its own line or inside a longer one (the model may join lines)
        if normalized not in tailored_counts and normalized not in tailored_text:
            warnings.append(f"Esta linha do seu currículo mudou ou sumiu: “{line.strip()}”")

    warnings += check_invented(original, tailored)

    original_counts = count_lines(original)
    for line, count in tailored_counts.items():
        if count > 1 and count > original_counts[line]:
            warnings.append(f"Linha repetida no currículo ajustado: “{line}”")

    lowered = tailored.casefold()
    gone = [item for item in skill_items(original) if item.casefold() not in lowered]
    if gone:
        warnings.append(f"Habilidades que sumiram: {', '.join(gone)}")
    return warnings


# --- Generation ---------------------------------------------------------------------


def ask_model(client: httpx.Client, config: LLMConfig, user_prompt: str) -> TailoringAnswer:
    last_error: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return parse_answer(plain_text(chat(client, config, SYSTEM_PROMPT, user_prompt)))
        # Only a malformed answer is worth asking again. A refused request (quota,
        # wrong model, bad key) isn't caught here, so its real message reaches the screen
        except LLMBadAnswerError as error:
            logger.warning("Tailoring attempt %d/%d failed: %s", attempt, ATTEMPTS, error)
            last_error = error
    raise LLMError("The model did not answer in the expected format") from last_error


def tailor_resume(
    session: Session, client: httpx.Client, config: LLMConfig, resume: str, job: Job
) -> TailoredResume:
    """Generate (or regenerate) the tailored resume for a job and save it."""
    # Log ids and sizes only: never the resume or the job text (CLAUDE.md)
    logger.info("Tailoring resume for %s with %s (%d chars)", job.id, config.model, len(resume))
    answer = ask_model(client, config, build_user_prompt(resume, job))
    warnings = check_preserved(resume, answer.resume)

    tailored = session.get(TailoredResume, job.id) or TailoredResume(
        job_id=job.id, content="", model=""
    )
    tailored.content = answer.resume.strip()
    tailored.changes = [item.strip() for item in answer.changes if item.strip()]
    tailored.missing = [item.strip() for item in answer.missing if item.strip()]
    tailored.warnings = warnings
    tailored.model = config.model
    tailored.created_at = utc_now()
    session.add(tailored)
    session.commit()
    session.refresh(tailored)
    logger.info("Tailored resume for %s saved, %d warnings", job.id, len(warnings))
    return tailored
