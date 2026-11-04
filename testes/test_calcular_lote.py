"""Testes do módulo 04 (calcular_lote).

Usam um resultado real do Slide (docs/amostras_slide2/resultados/r01_grid_bishop_janbu.zip) e um
aslidew.exe falso que só grava esse resultado no .slim, já que o motor de verdade só roda no Windows.
Rodar:  python testes/test_calcular_lote.py     (ou: pytest testes)
"""
import importlib.util
import io
import shutil
import sys
import tempfile
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import openpyxl  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("calcular_lote", RAIZ / "modulos" / "04_calculo_em_lote" / "calcular_lote.py")
cl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cl)

R01 = RAIZ / "docs" / "amostras_slide2" / "resultados" / "r01_grid_bishop_janbu.zip"
MODELO = RAIZ / "docs" / "amostras_slide2" / "busca" / "07_circular_grid_autogrid.slim"

FALSO = '''import sys, zipfile
from pathlib import Path
slim = Path(sys.argv[1])
s01 = zipfile.ZipFile(r"{r01}").read("r01.s01")
with zipfile.ZipFile(slim, "a") as z:
    z.writestr(slim.stem + ".s01", s01)
sys.exit(2)   # como o aslidew.exe de verdade: código 2 mesmo dando certo
'''
NADA = "import sys; sys.exit(2)\n"


def _resultado():
    with zipfile.ZipFile(R01) as z:
        return z.read("r01.s01").decode().replace("\r\n", "\n"), z.read("r01.sli").decode().replace("\r\n", "\n")


def test_le_resultado_real_do_slide():
    s01, sli = _resultado()
    res = cl.ler_resultado(s01)
    assert res["metodos"] == ["bishop simplified", "janbu simplified"]
    assert res["minimos"]["bishop simplified"]["fs"] == 0.316616
    assert res["minimos"]["janbu simplified"]["fs"] == 0.297976
    m = res["minimos"]["bishop simplified"]
    assert abs(m["xc"] - 29.870745771933) < 1e-9 and abs(m["r"] - 10.8988595509755) < 1e-9
    assert res["contadores"]["bishop simplified"] == (5853, 3)
    assert len(res["fatias"]["bishop simplified"]) > 10
    modelo = cl.ler_modelo(sli)
    assert len(modelo["grelhas"]) == 2 and modelo["modo"] == 0 and modelo["busca"] == 0
    avisos = cl.conferir(modelo, m)
    assert any("BORDA da grelha" in a for a in avisos) and len(avisos) == len(set(avisos))


def _rodar(script, fs_alvo="1.5"):
    d = Path(tempfile.mkdtemp())
    (d / "modelos").mkdir()
    shutil.copy(MODELO, d / "modelos" / "Secao_01.slim")
    falso = d / "aslidew_falso.py"
    falso.write_text(script.format(r01=R01), encoding="utf-8")
    cl.PREFS = d / "prefs.json"
    with redirect_stdout(io.StringIO()) as out:
        rc = cl.main([str(d / "modelos"), "--aslide", str(falso), "--fs-alvo", fs_alvo])
    return d, rc, out.getvalue()


def test_lote_com_motor_falso_gera_planilha():
    d, rc, out = _rodar(FALSO)
    assert rc == 0, out
    wb = openpyxl.load_workbook(d / "modelos" / "resultados.xlsx")
    linhas = list(wb["Resumo"].iter_rows(min_row=2, values_only=True))
    assert [l[1] for l in linhas] == ["Bishop simplificado", "Janbu simplificado"]
    assert linhas[0][2] == 0.3166 and linhas[0][4] == "não" and linhas[1][5] == "sim"   # Janbu é o crítico
    assert "BORDA da grelha" in linhas[0][16]
    assert len(wb["Figuras"]._images) == 1
    assert (d / "modelos" / "resultados_figuras" / "Secao_01.png").is_file()
    assert "aslidew_falso.py" in (d / "prefs.json").read_text(encoding="utf-8")  # caminho salvo


def test_lote_acusa_quando_o_motor_nao_grava_resultado():
    d, rc, out = _rodar(NADA)
    assert rc == 1 and "não gravou resultado" in out


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
