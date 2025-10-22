import streamlit as st
import re
from pathlib import Path

# caminho relativo para o arquivo HTML local (certifique-se que está na mesma pasta do cod.py)
HTML_PATH = Path(__file__).with_name("DEL2848compilado.html")

# Lista de crimes que queremos oferecer na UI — você pode editar/adicionar aqui
CRIME_KEYWORDS = [
    "Furto",
    "Roubo",
    "Homicídio doloso",
    "Estelionato",
    "Receptação"
]


def load_html_text(path: Path) -> str:
    if not path.exists():
        return ""
    # tenta abrir com encoding comum; o arquivo original parece windows-1252
    try:
        return path.read_text(encoding="windows-1252")
    except Exception:
        return path.read_text(encoding="utf-8", errors="ignore")


def parse_minimum_penalty_from_snippet(snippet: str):
    """
    Extrair o valor de pena (em anos) a partir de um trecho de texto.
    Procura padrões como:
      - 'de X a Y anos'
      - 'X a Y anos' -> pega X (pena mínima)
      - 'X a Y anos' -> pega Y (pena maxima)
    Retorna inteiro de anos
    s = snippet.lower()

    # pattern de intervalo: '(\d+) a (\d+) anos|meses'
    m = re.search(r'(\d+)\s*(?:a|até|-)\s*(\d+)\s*(anos|ano|meses|m[eê]s|mês)', s)
    if m:
        low = int(m.group(1))
        unit = m.group(3)
        if "ano" in unit:
            return low * 12
        return low


def extract_penalties_from_html(text: str, keywords):
    """
    Para cada keyword, procura sua ocorrência no texto e tenta extrair uma pena.
    Retorna dict: {keyword: penalty}
    """
    text_lower = text.lower()
    results = {}
    for kw in keywords:
        kw_lower = kw.lower()
        pos = text_lower.find(kw_lower)
        penalty = None
        if pos != -1:
            # pega janela ao redor da ocorrência para procurar menção à pena
            start = max(0, pos - 400)
            end = min(len(text), pos + 400)
            snippet = text[start:end]
            penalty = parse_minimum_penalty_from_snippet(snippet)

            # se não encontrou no trecho imediato, tenta procurar ocorrências adicionais
            if penalty is None:
                # procura próximas ocorrências de palavras 'pena', 'reclusão', 'detenção' próximas
                extra_pos = re.search(r'(pena|reclus[aã]o|detenç[aã]o)', text_lower[start:end])
                if extra_pos:
                    # ampliar a janela um pouco mais e tentar novamente
                    start2 = max(0, pos - 800)
                    end2 = min(len(text), pos + 800)
                    penalty = parse_minimum_penalty_from_snippet(text[start2:end2])

        results[kw] = penalty
    return results


def main():
    st.title("Calculadora de Dosimetria Penal (usando DEL2848compilado.html)")

    html_text = load_html_text(HTML_PATH)
    if not html_text:
        st.error(f"Arquivo {HTML_PATH.name} não encontrado. Coloque DEL2848compilado.html na mesma pasta de cod.py.")
        return

    st.markdown("Os valores de pena mínima tentam ser extraídos automaticamente do arquivo DEL2848compilado.html. Se não for possível encontrar a pena mínima para um crime, você poderá informá-la manualmente (em meses).")

    # extrai penalidades encontradas no HTML
    extracted = extract_penalties_from_html(html_text, CRIME_KEYWORDS)

    # interface para o usuário: mostrarmos os crimes e as penas (extraídas ou input manual)
    st.header("Fase 1: Pena Base")
    crime = st.selectbox("Selecione o tipo de crime:", CRIME_KEYWORDS)

    # mostra o valor extraído (se existir) e permite que o usuário modifique
    extracted_penalty = extracted.get(crime)
    if extracted_penalty is not None:
        st.info(f"Pena mínima extraída do HTML: {extracted_penalty} meses")
    else:
        st.warning("Pena mínima não encontrada automaticamente no HTML para este crime. Informe abaixo (em meses).")

    # permitir input manual (preenchido com extraído se houver)
    pena_minima = st.number_input("Pena mínima (meses):", min_value=0, step=1, value=int(extracted_penalty) if extracted_penalty else 0)

    circunstancias = st.number_input("Número de circunstâncias agravantes:", min_value=0, step=1, value=0)

    # cálculo pena base
    pena_base = pena_minima * (1 + circunstancias * 1/8)
    st.write(f"Pena mínima: {pena_minima} meses")
    st.write(f"Pena base após fase 1: {pena_base:.2f} meses")

    # Fase 2
    st.header("Fase 2: Circunstâncias")
    agravantes = st.number_input("Número de agravantes:", min_value=0, step=1, value=0)
    atenuantes = st.number_input("Número de atenuantes:", min_value=0, step=1, value=0)

    pena_fase2 = pena_base * (1 + agravantes * 1/6) * (1 - atenuantes * 1/6)
    st.write(f"Pena após fase 2: {pena_fase2:.2f} meses")

    # Fase 3
    st.header("Fase 3: Causas de aumento/diminução")
    majorantes = st.number_input("Percentual de majorantes (%):", min_value=0.0, step=1.0, value=0.0)
    minorantes = st.number_input("Percentual de minorantes (%):", min_value=0.0, step=1.0, value=0.0)

    pena_final = pena_fase2 * (1 + majorantes / 100) * (1 - minorantes / 100)

    st.header("Resultado Final")
    st.success(f"Pena final calculada: {pena_final:.2f} meses")

    # Conversão para anos/meses
    anos = int(pena_final // 12)
    meses = int(pena_final % 12)
    st.info(f"Equivalente a: {anos} anos e {meses} meses")

    # Mostrar resumo das extrações
    st.header("Resumo de extrações do HTML")
    for k, v in extracted.items():
        if v is None:
            st.write(f"- {k}: pena mínima não encontrada automaticamente.")
        else:
            st.write(f"- {k}: pena mínima detectada ≈ {v} meses")


if __name__ == "__main__":
    main()
