"""Testes do módulo 02 (cad_para_planilha).

Rodar:  python testes/test_cad_para_planilha.py     (ou: pytest testes)
"""
import importlib.util
import io
import math
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gerar_dxf_sinteticos as gerar  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "cad_para_planilha", RAIZ / "modulos" / "02_cad_para_planilha" / "cad_para_planilha.py")
cpp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpp)

import ezdxf  # noqa: E402
import openpyxl  # noqa: E402


def secoes_de(dxf, janelas, unidade="m", exagero=1.0, zerar_x=False, tol=0.001):
    doc = ezdxf.readfile(dxf)
    fator = cpp.UNIDADES[unidade]
    itens, _ = cpp.coletar(doc.modelspace(), 0.005 / fator)
    jans = cpp.parse_janelas(janelas)
    por, _, _ = cpp.atribuir(itens, jans)
    return [cpp.processar_secao(j["nome"], its, fator, exagero, zerar_x, tol, 1e-4) for j, its in zip(jans, por)]


def areas(sec):
    return sorted(round(r["area"], 3) for r in sec["regioes"])


def test_linhas_soltas_e_polilinhas_dao_as_mesmas_regioes():
    with tempfile.TemporaryDirectory() as d:
        dxf = Path(d) / "t.dxf"
        gerar.tres_camadas(dxf)
        s1, s2, s3 = secoes_de(dxf, "-5,-20,50,10;95,-20,150,10;195,-20,250,10")
    assert areas(s1) == areas(s2) == [258.0, 258.0, 258.0]
    assert s1["avisos"] == [] and s2["avisos"] == []  # o vértice em T não pode gerar lasca
    assert areas(s3) == [258.0, 516.0]


def test_falhas_de_desenho_furo_e_arco():
    with tempfile.TemporaryDirectory() as d:
        dxf = Path(d) / "c.dxf"
        gerar.casos_de_desenho(dxf)
        a, b, c, arco = secoes_de(dxf, "-5,-20,50,10;95,-20,150,10;195,-20,250,10;295,-20,350,10")
    # 0,4 mm < 1 mm: fecha (o encaixe move o canto em décimos de mm, por isso a comparação aproximada)
    assert a["avisos"] == [] and all(abs(x - y) < 0.05 for x, y in zip(areas(a), [258.0, 516.0]))
    assert areas(b) == [258.0]                                         # 10 cm: não fecha
    assert any("(143.000; -3.100)" in av for av in b["avisos"])        # e aponta onde (seção em x = 100)
    assert len(c["regioes"]) == 2 and any("furo" in av for av in c["avisos"])
    # fundo em arco (bulge 0,2 numa corda de 43 m): área = 774 - segmento circular
    teta = 4 * math.atan(0.2)
    r = 43 / (2 * math.sin(teta / 2))
    esperado = 774 - r * r / 2 * (teta - math.sin(teta))
    assert abs(arco["area_total"] - esperado) / esperado < 0.005


def test_exemplo_real_e_conversoes():
    dxf = RAIZ / "exemplos" / "duas_secoes_linhas_e_polilinha.dxf"
    jan = "0,-12,50,14;95,-12,145,14"
    s1, s2 = secoes_de(dxf, jan)
    assert areas(s1) == areas(s2) == [774.0]
    s1, _ = secoes_de(dxf, jan, exagero=2, zerar_x=True)
    assert areas(s1) == [387.0] and abs(s1["bbox"][0]) < 1e-9 and abs(s1["desloc_x"] - 3.353918) < 1e-5
    s1, _ = secoes_de(dxf, jan, unidade="cm")
    assert areas(s1) == [0.077]


def test_planilha_gerada():
    dxf = RAIZ / "exemplos" / "duas_secoes_linhas_e_polilinha.dxf"
    with tempfile.TemporaryDirectory() as d:
        saida = Path(d) / "s.xlsx"
        with redirect_stdout(io.StringIO()):
            rc = cpp.main([str(dxf), "--unidade", "m", "--exagero-vertical", "1", "--zerar-x", "n",
                           "--camadas", "0", "--janelas", "0,-12,50,14;95,-12,145,14", "--saida", str(saida)])
        assert rc == 0
        wb = openpyxl.load_workbook(saida)
        assert wb.sheetnames == ["LEIA-ME", "Materiais", "Secoes", "Regioes", "Vertices", "Previas", "Origem"]
        assert wb["Regioes"].max_row == 3
        dv = wb["Regioes"].data_validations.dataValidation[0]
        assert dv.formula1 == "=Materiais!$A$2:$A$21"
        assert len(wb["Previas"]._images) == 2
        assert saida.with_suffix(".json").is_file()
        # repetir com --config deve dar o mesmo resultado sem perguntas
        with redirect_stdout(io.StringIO()):
            rc = cpp.main(["--config", str(saida.with_suffix(".json")), "--saida", str(Path(d) / "r.xlsx")])
        assert rc == 0


def test_auto_agrupa_e_mostra_fusao_por_linha_comum():
    dxf = RAIZ / "exemplos" / "duas_secoes_linhas_e_polilinha.dxf"
    doc = ezdxf.readfile(dxf)
    itens, _ = cpp.coletar(doc.modelspace(), 0.005)
    assert len(cpp.detectar_grupos(itens, 0.001)) == 2
    doc.modelspace().add_line((3.353918, -9.511771), (142.458931, -9.511771))  # linha de base comum
    itens, _ = cpp.coletar(doc.modelspace(), 0.005)
    jans = cpp.detectar_grupos(itens, 0.001)
    assert len(jans) == 1
    with tempfile.TemporaryDirectory() as d:
        png = cpp.mostrar_janelas(itens, jans, Path(d) / "j.png")
        assert png.is_file()


def test_seletor_de_janelas():
    import matplotlib.pyplot as plt
    dxf = RAIZ / "exemplos" / "duas_secoes_linhas_e_polilinha.dxf"
    itens, _ = cpp.coletar(ezdxf.readfile(dxf).modelspace(), 0.005)
    s = cpp.SeletorJanelas(itens, plt)
    s.tecla(SimpleNamespace(key="enter"))
    assert s.janelas == []                       # ENTER sem retângulo não salva
    s.sel.extents = (0, 50, -12, 14)
    s.tecla(SimpleNamespace(key="enter"))
    s.sel.extents = (95, 145, -12, 14)
    s.tecla(SimpleNamespace(key="enter"))
    s.sel.extents = (60, 90, -12, 14)
    s.tecla(SimpleNamespace(key="enter"))
    s.tecla(SimpleNamespace(key="backspace"))    # desfaz a terceira
    assert [j["nome"] for j in s.janelas] == ["Secao_01", "Secao_02"]
    por, cortadas, fora = cpp.atribuir(itens, s.janelas)
    assert [len(p) for p in por] == [6, 2] and cortadas == [0, 0] and fora == 0
    plt.close("all")


def test_arquivos_recusados():
    with tempfile.TemporaryDirectory() as d:
        vazio = Path(d) / "v.dxf"
        vazio.write_bytes(b"")
        dwg = Path(d) / "x.dwg"
        dwg.write_bytes(b"AC1032")
        with redirect_stdout(io.StringIO()):
            assert cpp.main([str(vazio), "--unidade", "m"]) == 2
            assert cpp.main([str(dwg), "--unidade", "m"]) == 2


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
