"""Testes do módulo 03 (planilha_para_slim).

O teste principal reconstrói a amostra a02 (salva pelo próprio Slide2) a partir das mesmas
entradas e compara bloco a bloco: vértices, contorno, terreno, NA, cargas, materiais e métodos.
Rodar:  python testes/test_planilha_para_slim.py     (ou: pytest testes)
"""
import importlib.util
import io
import re
import sys
import tempfile
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import openpyxl  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


def _carregar(nome, rel):
    spec = importlib.util.spec_from_file_location(nome, RAIZ / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


p2s = _carregar("planilha_para_slim", "modulos/03_planilha_para_slim/planilha_para_slim.py")
cpp = _carregar("cad_para_planilha", "modulos/02_cad_para_planilha/cad_para_planilha.py")

A02 = RAIZ / "docs" / "amostras_slide2" / "a02_na_inclinado_carga_inclinada.slim"
NA_A02 = [(0, -6), (3.729, -7.909), (7.745, -9.899), (12.828, -9.899), (16.382, -9.899), (21.003, -9.899),
          (24.521, -9.366), (26.938, -8.406), (29.746, -7.624), (32.554, -6.629), (37.494, -6.629), (43, -6)]


def ler_sli(slim):
    with zipfile.ZipFile(slim) as z:
        return z.read([n for n in z.namelist() if n.endswith(".sli")][0]).decode("utf-8").replace("\r\n", "\n")


def bloco(texto, nome):
    m = re.search(rf"(?ms)^{re.escape(nome)}:\n(.*?)(?=^\S[^\n]*:\n|\Z)", texto)
    return m.group(1).strip() if m else ""


def coords(texto):
    v = {}
    for ln in bloco(texto, "vertices").splitlines():
        m = re.match(r"\s*(\d+) x: (\S+)\s+y: (\S+)", ln)
        v[int(m.group(1))] = (round(float(m.group(2)), 6) + 0.0, round(float(m.group(3)), 6) + 0.0)
    return v


def lista(texto, nome):
    m = re.search(r"vertices: \[([\d,]+)\]", bloco(texto, nome))
    return [int(i) for i in m.group(1).split(",")] if m else []


def secao_a02():
    materiais = {"Silte": {"nome": "Silte", "gamma": 18, "c": 10, "phi": 28, "slot": 1, "gsat": None, "cor": None},
                 "Argila": {"nome": "Argila", "gamma": 20, "c": 15, "phi": 25, "slot": 2, "gsat": None, "cor": None}}
    sec = {"n": 1, "nome": "a02", "cota_real": None, "regioes": {
        1: {"material": "Argila", "aneis": {0: [(0, 0), (0, -6), (23, -6), (20, 0)]}},
        2: {"material": "Silte", "aneis": {0: [(0, -15), (43, -15), (43, -6), (23, -6), (0, -6)]}}},
        "na": [(k, x, y, "planilha") for k, (x, y) in enumerate(NA_A02, 1)],
        "cargas": [{"linha_planilha": 2, "tipo": "distribuida", "xa": 0, "xb": 20, "q": 100, "angulo": None},
                   {"linha_planilha": 3, "tipo": "linha", "xa": 20, "xb": None, "q": 200, "angulo": 270},
                   {"linha_planilha": 4, "tipo": "linha", "xa": 28.1466919383044, "xb": None, "q": 100, "angulo": 330}]}
    return sec, materiais


def test_reconstroi_amostra_a02():
    sec, materiais = secao_a02()
    base = ler_sli(RAIZ / "modulos" / "01_modelo_basico" / "modelo_base" / "vazio.slim")
    geo = p2s.montar_secao(sec, materiais, "left to right")
    gerado = p2s.gerar_sli(base, geo, materiais, ["bishop", "janbu"])
    slide = ler_sli(A02)
    vg, vs = coords(gerado), coords(slide)
    # mesmos pontos, na mesma numeração (contorno 1-7, depois os pontos do NA)
    assert vg == vs, (vg, vs)
    for nome in ("exterior", "slope", "water table"):
        assert lista(gerado, nome) == lista(slide, nome), nome
    for chave in ("direction", "methods"):
        assert re.search(rf"(?m)^\s*{chave}:.*$", gerado).group(0) == re.search(rf"(?m)^\s*{chave}:.*$", slide).group(0)
    for k in (1, 2):
        lg = re.search(rf"(?m)^\s*soil{k} = .*$", gerado).group(0)
        ls = re.search(rf"(?m)^\s*soil{k} = .*$", slide).group(0)
        assert lg == ls, (lg, ls)
    for nome in ("forces", "dist load group", "stats params loads"):
        assert bloco(gerado, nome) == bloco(slide, nome), (nome, bloco(gerado, nome), bloco(slide, nome))
    assert re.search(r"(?m)^\s*x1: .*$", gerado).group(0) == re.search(r"(?m)^\s*x1: .*$", slide).group(0)
    # interface de material: mesmos pontos (a ordem de percurso pode diferir)
    tipo3 = lambda t: sorted(ln.split()[2] for ln in bloco(t, "geometry info").splitlines() if ln.split()[:1] == ["3"])
    pts3 = lambda t: sorted(tuple(round(float(c), 6) + 0.0 for c in s.split(",")) for s in tipo3(t))
    assert pts3(gerado) == pts3(slide)
    # células: cada uma com o material certo e cobrindo a seção inteira
    assert sum(1 for ln in bloco(gerado, "cells").splitlines() if ln.strip()) == len(geo["celulas"])


def test_gle_acrescenta_funcao_de_forcas():
    sec, materiais = secao_a02()
    base = ler_sli(RAIZ / "modulos" / "01_modelo_basico" / "modelo_base" / "vazio.slim")
    geo = p2s.montar_secao(sec, materiais, "right to left")
    t = p2s.gerar_sli(base, geo, materiais, ["gle", "spencer", "fellenius"])
    assert "methods: 137" in t and "side force function:\n  type: half_sine\n\nmaterial types:" in t
    assert "direction: right to left" in t


def test_fluxo_completo_cad_planilha_slim():
    dxf = RAIZ / "exemplos" / "quatro_secoes_em_grade.dxf"
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        xlsx = d / "secoes.xlsx"
        with redirect_stdout(io.StringIO()):
            assert cpp.main([str(dxf), "--unidade", "m", "--exagero-vertical", "1", "--zerar-x", "s",
                             "--camadas", "SECOES", "--camada-na", "", "--saida", str(xlsx),
                             "--janelas", "-3,-18,46,9;57,-19,106,11;-3,-57,46,-29;57,-57,106,-32"]) == 0
        wb = openpyxl.load_workbook(xlsx)
        for i, m in enumerate([("Aterro", 18, None, 5, 28, "#C8E6C9"), ("Argila", 17, None, 15, 24, None),
                               ("Silte", 19, None, 8, 31, None)], 2):
            for j, v in enumerate(m, 1):
                wb["Materiais"].cell(row=i, column=j, value=v)
        escolha = {1: ["Aterro", "Argila", "Silte"], 2: ["Aterro", "Argila", "Silte"], 3: ["Argila", "Silte"],
                   4: ["Silte", "Argila"]}
        for r in range(2, wb["Regioes"].max_row + 1):
            s, k = wb["Regioes"].cell(r, 1).value, wb["Regioes"].cell(r, 2).value
            wb["Regioes"].cell(r, 6, escolha[s][k - 1])
        wb["Secoes"].cell(3, 11, 112.0)                     # seção 2: cota real do topo = 112
        for k, (x, y) in enumerate([(0, -6), (20, -7), (43, -9)], 1):
            wb["NA"].append([1, k, x, y, "planilha"])
        for k, (x, y) in enumerate([(10, 100), (43, 102)], 1):  # seção 2 em cota real; NA curto à esquerda
            wb["NA"].append([2, k, x, y, "planilha"])
        wb["Cargas"]["A2"], wb["Cargas"]["B2"], wb["Cargas"]["C2"], wb["Cargas"]["D2"], wb["Cargas"]["E2"] = 1, "distribuida", 15, 30, 20
        wb["Cargas"]["A3"], wb["Cargas"]["B3"], wb["Cargas"]["C3"], wb["Cargas"]["E3"], wb["Cargas"]["F3"] = 3, "linha", 35, 50, 300
        wb.save(xlsx)
        saida = d / "modelos"
        with redirect_stdout(io.StringIO()) as out:
            rc = p2s.main([str(xlsx), "--direcao", "dir-esq", "--metodos", "1,9", "--superficie", "circular", "--busca", "autorefine", "--saida", str(saida)])
        assert rc == 0, out.getvalue()
        modelos = sorted(saida.glob("*.slim"))
        assert [m.stem for m in modelos] == ["Secao_01", "Secao_02", "Secao_03", "Secao_04"]
        t1 = ler_sli(saida / "Secao_01.slim")
        assert "methods: 10" in t1 and "direction: right to left" in t1
        assert len(lista(t1, "water table")) == 3
        assert bloco(t1, "dist load group").count("begin:") == 1
        assert len(bloco(t1, "forces").splitlines()) == 3     # 20 kPa de 15 a 30 passa pelo pé (x=20) e pela crista (x=23)
        t2 = ler_sli(saida / "Secao_02.slim")
        assert max(y for _, y in coords(t2).values()) == 112.0
        assert "o NA não cobria a seção inteira" in out.getvalue()
        t3 = ler_sli(saida / "Secao_03.slim")
        assert re.search(r"type: 1 x1: 35 y1: \S+ angle: 300 load: 50", t3)
        t4 = ler_sli(saida / "Secao_04.slim")
        assert "soil2" in bloco(t4, "cells") and "soil3" in bloco(t4, "cells")   # lente de argila no silte
        assert (saida / "respostas.json").is_file() and (saida / "Secao_04.png").is_file()
        # cabeçalhos ZIP novos (sem campos herdados do molde), senão o Slide recusa o arquivo
        for m in modelos:
            infos = zipfile.ZipFile(m).infolist()
            assert [i.filename for i in infos] == [m.stem + s for s in (".sli", ".slv", ".sltm")]
            assert all(i.extra == b"" for i in infos)
        # repetir pelo JSON, sem perguntas
        with redirect_stdout(io.StringIO()):
            assert p2s.main(["--config", str(saida / "respostas.json"), "--saida", str(d / "r")]) == 0


def test_codigos_de_busca_iguais_as_amostras_do_slide():
    """Cada combinação de superfície/busca grava os mesmos campos que o Slide gravou nas amostras."""
    sec, materiais = secao_a02()
    base = ler_sli(RAIZ / "modulos" / "01_modelo_basico" / "modelo_base" / "vazio.slim")
    geo = p2s.montar_secao(sec, materiais, "left to right")
    pasta = RAIZ / "docs" / "amostras_slide2" / "busca"
    casos = {"01_circular_slope_search.slim": ("circular", "slope"),
             "02_circular_auto_refine.slim": ("circular", "autorefine"),
             "03_nao_circular_block.slim": ("nao_circular", "block"),
             "04_nao_circular_path.slim": ("nao_circular", "path"),
             "05_nao_circular_simulated_annealing.slim": ("nao_circular", "annealing"),
             "06_nao_circular_auto_refine.slim": ("nao_circular", "autorefine")}
    campo = lambda t, c: re.search(rf"(?m)^\s*{c}:.*$", t).group(0)
    for arq, (tipo, metodo) in casos.items():
        slide = ler_sli(pasta / arq)
        geo["grelha"] = None
        t = p2s.gerar_sli(base, geo, materiais, ["bishop", "janbu"], {"tipo": tipo, "metodo": metodo})
        for c in ("mode", "circularsearch", "search"):
            if tipo == "circular" and c == "search" or tipo != "circular" and c == "circularsearch":
                continue
            assert campo(t, c) == campo(slide, c), (arq, c, campo(t, c), campo(slide, c))
    # grelha: mesma linha que o Slide grava
    slide = ler_sli(pasta / "07_circular_grid_autogrid.slim")
    m = re.search(r"x1: (\S+) y1: (\S+)  x2: (\S+) y2: (\S+)  nx: (\d+) ny: (\d+)", bloco(slide, "grids"))
    geo["grelha"] = tuple(float(v) for v in m.groups()[:4]) + (int(m.group(5)), int(m.group(6)))
    t = p2s.gerar_sli(base, geo, materiais, ["bishop"], {"tipo": "circular", "metodo": "grid"})
    assert bloco(t, "grids") == bloco(slide, "grids")
    assert campo(t, "mode") == "  mode: 0" and campo(t, "circularsearch") == "  circularsearch: 0"


def test_grelha_do_script_fica_acima_da_face():
    terreno = [(0, 0), (20, 0), (23, 6), (43, 6)]
    assert p2s.grelha_do_script(terreno, "right to left") == (11.0, 6.0, 26.0, 18.0, 20, 20)
    assert p2s.grelha_do_script(terreno, "left to right") == (17.0, 6.0, 32.0, 18.0, 20, 20)
    # centro crítico achado pelo Auto Refine do Slide nessa seção (teste no Slide 6.0): dentro da grelha
    x1, y1, x2, y2, _, _ = p2s.grelha_do_script(terreno)
    assert x1 < 13.13 < x2 and y1 < 11.06 < y2


def test_erros_claros():
    sec, materiais = secao_a02()
    sec["regioes"][1]["material"] = None
    try:
        p2s.montar_secao(sec, materiais, "left to right")
        assert False
    except p2s.ErroSecao as e:
        assert "sem material" in str(e)
    sec, materiais = secao_a02()
    sec["cargas"] = [{"linha_planilha": 9, "tipo": "linha", "xa": 99, "xb": None, "q": 1, "angulo": None}]
    try:
        p2s.montar_secao(sec, materiais, "left to right")
        assert False
    except p2s.ErroSecao as e:
        assert "fora do terreno" in str(e)


if __name__ == "__main__":
    falhas = 0
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok    {nome}")
            except Exception as exc:  # noqa: BLE001
                falhas += 1
                print(f"FALHA {nome}: {exc!r}")
    print(f"\n{'Tudo certo.' if not falhas else f'{falhas} teste(s) falharam.'}")
    sys.exit(1 if falhas else 0)
