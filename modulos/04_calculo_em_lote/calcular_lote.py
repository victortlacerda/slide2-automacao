#!/usr/bin/env python3
"""Calcula em lote modelos Slide2 (.slim) com o motor aslidew.exe e tabela o FS de cada seção.

Para cada modelo da pasta:
    1. roda  aslidew.exe "modelo.slim"  (o resultado é gravado dentro do .slim, membro .s01);
    2. lê o FS mínimo global de cada método e a superfície crítica;
    3. confere: mínimo na borda da grelha, superfície no limite de busca ou no fundo do modelo,
       FS abaixo do FS-alvo (se informado);
    4. gera resultados.xlsx (resumo + figuras) e um PNG por seção com a superfície crítica.

Uso:
    python calcular_lote.py                                  # escolhe a pasta numa janela
    python calcular_lote.py pasta_dos_modelos --aslide "C:\\...\\aslidew.exe" --fs-alvo 1.5
    python calcular_lote.py --somente-ler pasta             # só lê resultados já calculados

O caminho do aslidew.exe fica salvo em ~/.slide2_automacao.json depois da primeira vez.
Atenção: o aslidew.exe devolve código de saída 2 mesmo quando calcula; o script confere pelo .s01.
Dependências:  pip install openpyxl matplotlib
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

try:
    import openpyxl
    from openpyxl.drawing.image import Image as XlImage
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
except ImportError as exc:  # pragma: no cover
    sys.exit(f"Falta a biblioteca '{exc.name}'. Instale com:\n  pip install openpyxl matplotlib")

VERSAO = "0.1"
PREFS = Path.home() / ".slide2_automacao.json"
NOMES_METODO = {
    "bishop simplified": "Bishop simplificado", "janbu simplified": "Janbu simplificado",
    "janbu corrected": "Janbu corrigido", "spencer": "Spencer", "gle/morgenstern-price": "GLE / M-P",
    "ordinary/fellenius": "Fellenius", "corps of engineers #1": "Corps #1", "corps of engineers #2": "Corps #2",
    "lowe-karafiath": "Lowe-Karafiath",
}


# ----------------------------------------------------------------------------
# Leitura do modelo e do resultado
# ----------------------------------------------------------------------------
def membros(slim):
    with zipfile.ZipFile(slim) as z:
        return {Path(n).suffix.lower(): z.read(n).decode("utf-8", "replace").replace("\r\n", "\n") for n in z.namelist()}


def _bloco(texto, nome):
    m = re.search(rf"(?ms)^{re.escape(nome)}:\n(.*?)(?=^\S[^\n]*:\n|\Z)", texto)
    return m.group(1) if m else ""


def _campo(texto, nome, padrao=None):
    m = re.search(rf"(?m)^\s*{re.escape(nome)}:\s*(\S+)", texto)
    return m.group(1) if m else padrao


def ler_modelo(sli):
    """Geometria mínima para conferir e desenhar: vértices, contorno, terreno, NA, células, grelhas."""
    v = {}
    for ln in _bloco(sli, "vertices").splitlines():
        m = re.match(r"\s*(\d+) x: (\S+)\s+y: (\S+)", ln)
        if m:
            v[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))
    lista = lambda nome: [int(i) for i in (re.search(r"vertices: \[([\d,]+)\]", _bloco(sli, nome)) or
                                            re.search(r"()", "")).group(1).split(",") if i]
    celulas = []
    for ln in _bloco(sli, "cells").splitlines():
        m = re.match(r"\s*\d+\s+vertices: \[(\d+),(\d+),(\d+)\] material: soil(\d+)", ln)
        if m:
            celulas.append(([int(m.group(i)) for i in (1, 2, 3)], int(m.group(4))))
    grelhas = []
    for ln in _bloco(sli, "grids").splitlines():
        m = re.search(r"x1: (\S+) y1: (\S+)\s+x2: (\S+) y2: (\S+)\s+nx: (\d+) ny: (\d+)", ln)
        if m:
            g = [float(m.group(i)) for i in range(1, 5)]
            grelhas.append((min(g[0], g[2]), min(g[1], g[3]), max(g[0], g[2]), max(g[1], g[3]),
                            int(m.group(5)), int(m.group(6))))
    modo = int(_campo(sli, "mode", 0))
    busca = int(_campo(sli, "circularsearch" if modo == 0 else "search", 0))
    lim = re.search(r"(?m)^\s*x1: (\S+) y1: (\S+) x2: (\S+) y2: (\S+)\s*$", sli)
    return {
        "v": v, "contorno": [v[i] for i in lista("exterior")], "terreno": [v[i] for i in lista("slope")],
        "na": [v[i] for i in lista("water table")], "celulas": [([v[i] for i in ids], s) for ids, s in celulas],
        "grelhas": grelhas, "modo": modo, "busca": busca,
        "direcao": (re.search(r"(?m)^\s*direction:\s*(.+)$", sli) or re.search(r"(.*)", "?")).group(1).strip(),
        "limites": tuple(float(lim.group(i)) for i in range(1, 5)) if lim else None,
    }


def ler_resultado(s01):
    """FS mínimo global por método e a superfície crítica (fatias) de cada um."""
    linhas = s01.split("\n")
    res = {"metodos": [], "minimos": {}, "fatias": {}, "contadores": {}}
    i = 0
    while i < len(linhas):
        ln = linhas[i].strip()
        if ln.startswith("* Analysis names"):
            n = int(linhas[i - 1].strip()) if linhas[i - 1].strip().isdigit() else 0
            res["metodos"] = [linhas[i + 1 + k].strip() for k in range(n)]
        elif ln.startswith("* Global Minimum FS"):
            j = i + 1
            while j < len(linhas) and not linhas[j].startswith("*"):
                partes = linhas[j].split()
                nums = []
                for p in partes:
                    try:
                        nums.append(float(p))
                    except ValueError:
                        break
                nome = " ".join(partes[len(nums):]).strip().lower()
                if nums and nome:
                    d = {"fs": nums[-1], "nums": nums}
                    if len(nums) == 8:  # circular: xc yc r x1 y1 x2 y2 fs
                        d.update(dict(zip(("xc", "yc", "r", "x1", "y1", "x2", "y2"), nums[:7])))
                    res["minimos"][nome] = d
                j += 1
            i = j
            continue
        elif ln.startswith("* minimum slice info") and "method=" in ln:
            nome = ln.split("method=")[1].strip().lower()
            pts, j = [], i + 1
            while j < len(linhas) and not linhas[j].startswith("*"):
                p = linhas[j].split()
                if len(p) >= 3:
                    try:
                        pts.append((float(p[0]), float(p[2])))
                    except ValueError:
                        break
                j += 1
            res["fatias"][nome] = pts
            i = j
            continue
        elif ln.startswith("* method name") and "valid" in ln:
            j = i + 1
            while j < len(linhas) and linhas[j].strip() and not linhas[j].startswith("*"):
                m = re.match(r"\s*(.+?)\s+(\d+)\s+(\d+)\s*$", linhas[j])
                if m:
                    res["contadores"][m.group(1).strip().lower()] = (int(m.group(2)), int(m.group(3)))
                j += 1
        i += 1
    return res


def conferir(modelo, minimo):
    """Checklist do guia: mínimo na borda da grelha, superfície no limite de busca ou no fundo."""
    avisos = []
    if minimo["fs"] <= 0:
        return ["nenhuma superfície válida encontrada (FS inválido)"]
    if "xc" in minimo and modelo["modo"] == 0 and modelo["busca"] == 0:
        for (x1, y1, x2, y2, nx, ny) in modelo["grelhas"]:
            dx, dy = (x2 - x1) / max(nx, 1), (y2 - y1) / max(ny, 1)
            dentro = x1 - dx / 2 <= minimo["xc"] <= x2 + dx / 2 and y1 - dy / 2 <= minimo["yc"] <= y2 + dy / 2
            if dentro and (abs(minimo["xc"] - x1) < dx / 2 or abs(minimo["xc"] - x2) < dx / 2 or
                           abs(minimo["yc"] - y1) < dy / 2 or abs(minimo["yc"] - y2) < dy / 2):
                avisos.append("centro crítico na BORDA da grelha: amplie ou desloque a grelha e calcule de novo")
    if modelo["limites"] and "x1" in minimo:
        lx1, _, lx2, _ = modelo["limites"]
        tol = 1e-3 * max(abs(lx2 - lx1), 1)
        if min(abs(minimo["x1"] - lx1), abs(minimo["x2"] - lx1), abs(minimo["x1"] - lx2), abs(minimo["x2"] - lx2)) < tol:
            avisos.append("superfície crítica no limite de busca (entrada/saída na ponta do terreno)")
    if modelo["contorno"] and "yc" in minimo:
        fundo = min(y for _, y in modelo["contorno"])
        if minimo["yc"] - minimo["r"] < fundo + 1e-3 * max(minimo["r"], 1):
            avisos.append("o círculo crítico chega ao fundo do modelo: aprofunde o contorno")
    return list(dict.fromkeys(avisos))


# ----------------------------------------------------------------------------
# Cálculo
# ----------------------------------------------------------------------------
def assinatura_s01(slim):
    with zipfile.ZipFile(slim) as z:
        s = [i for i in z.infolist() if i.filename.lower().endswith(".s01")]
        return (s[0].CRC, s[0].file_size) if s else None


def calcular(aslide, slim, timeout):
    antes = assinatura_s01(slim)
    cmd = [sys.executable, str(aslide), str(slim)] if str(aslide).endswith(".py") else [str(aslide), str(slim)]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(slim.parent), timeout=timeout, capture_output=True)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"o cálculo passou de {timeout} s")
    depois = assinatura_s01(slim)
    if depois is None:
        raise RuntimeError(f"o aslidew.exe não gravou resultado (código {proc.returncode})")
    if antes is not None and depois == antes and slim.stat().st_mtime < t0:
        raise RuntimeError("o resultado não foi atualizado")
    return time.time() - t0


# ----------------------------------------------------------------------------
# Saídas
# ----------------------------------------------------------------------------
def desenhar(nome, modelo, res, metodo_critico, caminho):
    from matplotlib.figure import Figure
    from matplotlib.patches import Polygon as MPoly, Rectangle
    paleta = ["#C8E6C9", "#FFF59D", "#FFCC80", "#B3E5FC", "#F8BBD0", "#D1C4E9", "#DCEDC8", "#FFE0B2"]
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=(11, 5.2), dpi=110)
    FigureCanvasAgg(fig)   # canvas explícito: evita aviso do matplotlib 3.3 (Anaconda)
    ax = fig.subplots()
    for pts, s in modelo["celulas"]:
        ax.add_patch(MPoly(pts, closed=True, fc=paleta[(s - 1) % len(paleta)], ec="none"))
    if modelo["contorno"]:
        ax.add_patch(MPoly(modelo["contorno"], closed=True, fill=False, ec="0.35", lw=1))
    if modelo["terreno"]:
        xs, ys = zip(*modelo["terreno"])
        ax.plot(xs, ys, color="0.15", lw=1.8)
    if modelo["na"]:
        xs, ys = zip(*modelo["na"])
        ax.plot(xs, ys, color="#1565C0", lw=1.4)
    for (x1, y1, x2, y2, nx, ny) in modelo["grelhas"]:
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, ec="#6A1B9A", lw=0.8, ls="--"))
    m = res["minimos"].get(metodo_critico)
    fatias = res["fatias"].get(metodo_critico)
    if fatias:
        xs, ys = zip(*fatias)
        ax.plot(xs, ys, color="#C62828", lw=2.2)
        if m and "xc" in m:
            ax.plot([m["xc"], xs[0]], [m["yc"], ys[0]], color="#C62828", lw=0.6, ls=":")
            ax.plot([m["xc"], xs[-1]], [m["yc"], ys[-1]], color="#C62828", lw=0.6, ls=":")
            ax.plot([m["xc"]], [m["yc"]], "o", color="#C62828", ms=4)
    if m:
        fs_txt = " | ".join(f"{NOMES_METODO.get(k, k)} {v['fs']:.3f}" for k, v in res["minimos"].items())
        ax.set_title(f"{nome}  |  FS mínimo: {fs_txt}", fontsize=9)
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.margins(0.05)
    ax.grid(alpha=0.3)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("cota (m)")
    fig.tight_layout()
    fig.savefig(caminho)


def gravar_xlsx(caminho, linhas, figuras, meta):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Resumo"
    cab = ["Seção (arquivo)", "Método", "FS mínimo", "FS-alvo", "Atende?", "Crítico da seção?", "xc", "yc", "r",
           "Entrada x", "Entrada y", "Saída x", "Saída y", "Superfícies válidas", "Inválidas", "Tempo (s)", "Avisos"]
    ws.append(cab)
    for c in range(1, len(cab) + 1):
        cel = ws.cell(row=1, column=c)
        cel.font = Font(bold=True, color="FFFFFF")
        cel.fill = PatternFill("solid", fgColor="305496")
        cel.alignment = Alignment(wrap_text=True, vertical="center")
    ws.freeze_panes = "A2"
    vermelho, verde = PatternFill("solid", fgColor="F8CBAD"), PatternFill("solid", fgColor="C6EFCE")
    for ln in linhas:
        ws.append([ln.get(k) for k in ("arquivo", "metodo", "fs", "fs_alvo", "atende", "critico", "xc", "yc", "r",
                                       "x1", "y1", "x2", "y2", "validas", "invalidas", "tempo", "avisos")])
        if ln.get("atende") in ("sim", "não"):
            ws.cell(row=ws.max_row, column=5).fill = verde if ln["atende"] == "sim" else vermelho
        if ln.get("avisos"):
            ws.cell(row=ws.max_row, column=17).fill = PatternFill("solid", fgColor="FFF2CC")
    for i, w in enumerate([26, 20, 10, 9, 9, 10, 9, 9, 8, 10, 10, 10, 10, 11, 9, 9, 80], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 32
    wf = wb.create_sheet("Figuras")
    r = 1
    for nome, png in figuras:
        if not Path(png).is_file():
            continue
        wf.cell(row=r, column=1, value=nome).font = Font(bold=True, size=12)
        img = XlImage(str(png))
        esc = 900 / img.width
        img.width, img.height = int(img.width * esc), int(img.height * esc)
        wf.add_image(img, f"A{r + 1}")
        r += int(img.height / 20) + 4
    wo = wb.create_sheet("Origem")
    for k, v in meta.items():
        wo.append([k, json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v])
    wo.column_dimensions["A"].width = 22
    wo.column_dimensions["B"].width = 100
    wb.save(caminho)


# ----------------------------------------------------------------------------
# Programa principal
# ----------------------------------------------------------------------------
def carregar_prefs():
    try:
        return json.loads(PREFS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def perguntar(texto, padrao=None):
    sufixo = f" [{padrao}]" if padrao else ""
    r = input(f"{texto}{sufixo}: ").strip().strip('"')
    return r or (padrao or "")


def escolher_pasta():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        p = filedialog.askdirectory(title="Pasta com os modelos .slim (saída do módulo 03)")
    finally:
        root.destroy()
    if not p:
        raise RuntimeError("Nenhuma pasta escolhida.")
    return Path(p)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Calcula modelos .slim em lote e tabela o FS.")
    ap.add_argument("entrada", nargs="*", type=Path, help="Pasta com .slim ou arquivos .slim")
    ap.add_argument("--aslide", type=Path, help="Caminho do aslidew.exe (fica salvo para as próximas vezes)")
    ap.add_argument("--fs-alvo", type=float, help="FS mínimo exigido (sem ele, só reporta)")
    ap.add_argument("--somente-ler", action="store_true", help="Não calcula: só lê resultados já gravados")
    ap.add_argument("--timeout", type=int, default=600, help="Tempo máximo por modelo, em segundos")
    ap.add_argument("--saida", type=Path, help="Planilha de resultados (padrão: <pasta>/resultados.xlsx)")
    args = ap.parse_args(argv)
    try:
        entradas = args.entrada or [escolher_pasta()]
        modelos = []
        for e in entradas:
            e = e.expanduser().resolve()
            modelos += sorted(e.glob("*.slim")) if e.is_dir() else [e]
        modelos = [m for m in modelos if m.suffix.lower() == ".slim" and m.is_file()]
        if not modelos:
            raise ValueError("Nenhum arquivo .slim encontrado.")
        pasta = modelos[0].parent
        prefs = carregar_prefs()
        aslide = None
        if not args.somente_ler:
            aslide = args.aslide or (Path(prefs["aslide"]) if prefs.get("aslide") else None)
            if aslide is None or not aslide.is_file():
                aslide = Path(perguntar("Caminho completo do aslidew.exe (na pasta do Slide)",
                                        str(aslide) if aslide else None))
            if not aslide.is_file():
                raise ValueError(f"aslidew.exe não encontrado: {aslide}")
            prefs["aslide"] = str(aslide)
            try:
                PREFS.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass
        fs_alvo = args.fs_alvo
        if fs_alvo is None and sys.stdin.isatty():
            r = perguntar("FS-alvo para conferir (Enter = só reportar)")
            fs_alvo = float(r.replace(",", ".")) if r else None

        print(f"\n{len(modelos)} modelo(s) em {pasta}")
        linhas, figuras = [], []
        dir_fig = pasta / "resultados_figuras"
        dir_fig.mkdir(exist_ok=True)
        for slim in modelos:
            nome = slim.stem
            try:
                tempo = None
                if not args.somente_ler:
                    tempo = calcular(aslide, slim, args.timeout)
                arq = membros(slim)
                if ".s01" not in arq:
                    raise RuntimeError("o modelo não tem resultado calculado")
                modelo = ler_modelo(arq[".sli"])
                res = ler_resultado(arq[".s01"])
                if not res["minimos"]:
                    raise RuntimeError("não encontrei o FS mínimo no resultado")
                validos = {k: v for k, v in res["minimos"].items() if v["fs"] > 0}
                critico = min(validos, key=lambda k: validos[k]["fs"]) if validos else None
                for metodo, m in res["minimos"].items():
                    av = conferir(modelo, m)
                    val, inv = res["contadores"].get(metodo, (None, None))
                    atende = None
                    if fs_alvo is not None and m["fs"] > 0:
                        atende = "sim" if m["fs"] >= fs_alvo else "não"
                    linhas.append({"arquivo": nome, "metodo": NOMES_METODO.get(metodo, metodo),
                                   "fs": round(m["fs"], 4) if m["fs"] > 0 else "inválido",
                                   "fs_alvo": fs_alvo, "atende": atende, "critico": "sim" if metodo == critico else "",
                                   **{k: (round(m[k], 4) if k in m else None) for k in ("xc", "yc", "r", "x1", "y1", "x2", "y2")},
                                   "validas": val, "invalidas": inv,
                                   "tempo": round(tempo, 1) if tempo is not None else None, "avisos": " | ".join(av)})
                png = dir_fig / f"{nome}.png"
                try:  # a figura é um extra: se o matplotlib falhar, a tabela de resultados sai assim mesmo
                    desenhar(nome, modelo, res, critico, png)
                    figuras.append((nome, png))
                except Exception as exc:  # noqa: BLE001
                    print(f"  aviso: figura de {nome} não gerada ({type(exc).__name__}: {str(exc).splitlines()[0][:120]})")
                resumo = ", ".join(f"{NOMES_METODO.get(k, k)} {v['fs']:.3f}" for k, v in res["minimos"].items())
                av = conferir(modelo, res["minimos"][critico]) if critico else ["sem FS válido"]
                print(f"  ok  {nome}: {resumo}" + (f" ({tempo:.1f} s)" if tempo is not None else "")
                      + (f"  AVISOS: {' | '.join(av)}" if av else ""))
            except (RuntimeError, OSError, zipfile.BadZipFile, KeyError) as exc:
                linhas.append({"arquivo": nome, "avisos": f"ERRO: {exc}"})
                print(f"  ERRO {nome}: {exc}")
        destino = (args.saida or pasta / "resultados.xlsx").expanduser().resolve()
        if destino.exists():
            destino = destino.with_name(f"{destino.stem}_{datetime.now():%Y%m%d_%H%M%S}{destino.suffix}")
        gravar_xlsx(destino, linhas, figuras, {"versao_script": VERSAO, "data": datetime.now().isoformat(timespec="seconds"),
                                               "aslide": str(aslide) if aslide else "(somente leitura)",
                                               "fs_alvo": fs_alvo, "modelos": [m.name for m in modelos]})
        print(f"\nResultados: {destino}")
        return 0 if all(not str(l.get("avisos", "")).startswith("ERRO") for l in linhas) else 1
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("\nOperação cancelada.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
