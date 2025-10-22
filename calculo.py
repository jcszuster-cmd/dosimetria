import streamlit as st
import re
from pathlib import Path

# tenta importar BeautifulSoup (opcional, melhora parsing de HTML)
try:
    from bs4 import BeautifulSoup  # type: ignore
    BS4_AVAILABLE = True
except Exception:
    BS4_AVAILABLE = False

# caminho relativo para o arquivo HTML local
HTML_PATH = Path(__file__).with_name("DEL2848compilado.html")

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
    try:
        return path.read_text(encoding="windows-1252")
    except Exception:
        return path.read_text(encoding="utf-8", errors="ignore")


def parse_minimum_penalty_from_snippet(snippet: str):
    """
    Extrair o valor de pena (em meses) a partir de um trecho de texto.
    Retorna inteiro (meses) ou None.
    """
    if not snippet:
        return None

    s = snippet.lower()

    # 1) intervalo: 'de X a Y anos' ou 'X a Y anos' -> pega X (pena mínima)
    m = re.search(r'(\d+)\s*(?:a|até|-)\s*(\d+)\s*(anos?|ano|meses?|m[eê]s|mês)\b', s)
    if m:
        low = int(m.group(1))
        unit = m.group(3)
        if "ano" in unit:
            return low * 12
        return low

    # 2) 'pena de X anos' ou 'reclusão de X meses' / 'detenção de X anos'
    m2 = re.search(r'(?:pena|reclus[aã]o|detenç[aã]o)[^\d]{0,40}(\d+)\s*(anos?|ano|meses?|m[eê]s|mês)\b', s)
    if m2:
        val = int(m2.group(1))
        unit = m2.group(2)
        if "ano" in unit:
            return val * 12
        return val

    # 3) isolado 'X anos' próximo ao termo (padrão genérico)
    m3 = re.search(r'(\d+)\s*(anos?|ano|meses?|m[eê]s|mês)\b', s)
    if m3:
        val = int(m3.group(1))
        unit = m3.group(2)
        if "ano" in unit:
            return val * 12
        return val

    return None


def extract_penalties_from_html(text: str, keywords, debug=False):
    """
    Para cada keyword, procura todas as ocorrências no texto (insensível a case),
    testa janelas maiores ao redor e, se disponível, usa BeautifulSoup para obter
    os textos visíveis mais próximos. Retorna dict {keyword: {"penalty": int|None, "debug": [...]}}
    """
    results = {}
    text_lower = text.lower()

    # opcional: parse com BeautifulSoup para obter o texto "visível" organizado por tags
    soup_text = None
    if BS4_AVAILABLE:
        try:
            soup = BeautifulSoup(text, "html.parser")
            # concatenar blocos de texto por bloco (parágrafo, li, td, th, h*)
            blocks = []
            for tag in soup.find_all(["p", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "div"]):
                t = tag.get_text(separator=" ", strip=True)
                if t:
                    blocks.append(t)
            soup_text = "\n".join(blocks).lower()
        except Exception:
            soup_text = None

    for kw in keywords:
        kw_lower = kw.lower()
        penalties_found = []
        debug_info = []

        # procurar todas as ocorrências do crime no texto plano
        for mpos in re.finditer(re.escape(kw_lower), text_lower):
            pos = mpos.start()
            # janela grande ao redor (primeiro tentamos +/- 1000)
            start = max(0, pos - 1000)
            end = min(len(text_lower), pos + 1000)
            snippet = text[start:end]
            penalty = parse_minimum_penalty_from_snippet(snippet)
            debug_info.append({"method": "plain_window_1000", "snippet": snippet[:800] + ("..." if len(snippet) > 800 else ""), "penalty": penalty})
            if penalty is not None:
                penalties_found.append((penalty, snippet))

            # se não encontrou, tentar janela ainda maior
            if penalty is None:
                start2 = max(0, pos - 3000)
                end2 = min(len(text_lower), pos + 3000)
                snippet2 = text[start2:end2]
                penalty2 = parse_minimum_penalty_from_snippet(snippet2)
                debug_info.append({"method": "plain_window_3000", "snippet": snippet2[:800] + ("..." if len(snippet2) > 800 else ""), "penalty": penalty2})
                if penalty2 is not None:
                    penalties_found.append((penalty2, snippet2))

        # se BeautifulSoup disponível, procurar nos blocos processados (úteis quando o HTML tem tabelas)
        if BS4_AVAILABLE and soup_text:
            for mpos in re.finditer(re.escape(kw_lower), soup_text):
                pos = mpos.start()
                start = max(0, pos - 500)
                end = min(len(soup_text), pos + 500)
                snippet = soup_text[start:end]
                penalty = parse_minimum_penalty_from_snippet(snippet)
                debug_info.append({"method": "bs4_blocks_500", "snippet": snippet[:800] + ("..." if len(snippet) > 800 else ""), "penalty": penalty})
                if penalty is not None:
                    penalties_found.append((penalty, snippet))

        # se nada encontrado por ocorrências diretas, tentar procurar padrões que combinem crime + 'pena' em proximidade
        if not penalties_found:
            pattern = re.compile(r'({kw}).{0,200}(pena|reclus[aã]o|detenç[aã]o).{0,200}'.format(kw=re.escape(kw_lower)), re.IGNORECASE | re.DOTALL)
            m = pattern.search(text_lower)
            if m:
                pos = max(0, m.start() - 500)
                end = min(len(text_lower), m.end() + 500)
                snippet = text[pos:end]
                penalty = parse_minimum_penalty_from_snippet(snippet)
                debug_info.append({"method": "crime_plus_pena_pattern", "snippet": snippet[:800] + ("..." if len(snippet) > 800 else ""), "penalty": penalty})
                if penalty is not None:
                    penalties_found.append((penalty, snippet))

        # escolhe a menor pena mínima encontrada (se houver múltiplas ocorrências)
        chosen_penalty = None
        if penalties_found:
            # penalidades_found é lista de (penalty, snippet) -> escolher menor penalty
            chosen_penalty = min(p[0] for p in penalties_found)

        results[kw] = {"penalty": chosen_penalty, "debug": debug_info}
    return results


def main():
    st.title("Calculadora de Dosimetria Penal (usando DEL2848compilado.html)")

    html_text = load_html_text(HTML_PATH)
    if not html_text:
        st.error(f"Arquivo {HTML_PATH.name} não encontrado. Coloque DEL2848compilado.html na mesma pasta de cod.py.")
        return

    st.markdown(
        "Os valores de pena mínima tentam ser extraídos automaticamente do arquivo "
        "DEL2848compilado.html. Se não for possível encontrar a pena mínima para um crime, "
        "você poderá informá-la manualmente (valores em meses)."
    )

    debug_mode = st.checkbox("Mostrar debug de extração", value=False)

    extracted_wrapped = extract_penalties_from_html(html_text, CRIME_KEYWORDS, debug=debug_mode)

    # interface para o usuário
    st.header("Fase 1: Pena Base")
    crime = st.selectbox("Selecione o tipo de crime:", CRIME_KEYWORDS)

    extracted_info = extracted_wrapped.get(crime, {})
    extracted_penalty = extracted_info.get("penalty") if extracted_info else None

    if extracted_penalty is not None:
        st.info(f"Pena mínima extraída do HTML: {extracted_penalty} meses")
    else:
        st.warning("Pena mínima não encontrada automaticamente no HTML para este crime. Informe abaixo (em meses).")

    # permitir input manual (preenchido com extraído se houver)
    pena_minima = st.number_input("Pena mínima (meses):", min_value=0, step=1, value=int(extracted_penalty) if extracted_penalty is not None else 0)

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

    # Mostrar resumo das extrações (sem debug)
    st.header("Resumo de extrações do HTML")
    for k, info in extracted_wrapped.items():
        v = info.get("penalty")
        if v is None:
            st.write(f"- {k}: pena mínima não encontrada automaticamente.")
        else:
            st.write(f"- {k}: pena mínima detectada ≈ {v} meses")

    # Se debug estiver ativo, mostrar detalhes por crime
    if debug_mode:
        st.header("Debug detalhado da extração")
        for k, info in extracted_wrapped.items():
            st.subheader(k)
            st.write(f"Penalidade escolhida: {info.get('penalty')}")
            debug_list = info.get("debug", [])
            if not debug_list:
                st.write("Sem tentativas de extração (nenhuma ocorrência encontrada).")
            else:
                for i, d in enumerate(debug_list, start=1):
                    st.write(f"#{i} método: {d.get('method')}, penalty: {d.get('penalty')}")
                    # mostra o snippet truncado (expandir se necessário)
                    st.text(d.get("snippet")[:2000])

if __name__ == "__main__":
    main()
