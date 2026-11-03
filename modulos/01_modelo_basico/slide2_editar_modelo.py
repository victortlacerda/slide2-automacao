#!/usr/bin/env python3
"""Cria um modelo Slide2 a partir de uma boundary poligonal arbitrária.

O utilizador fornece os vértices da boundary externa em ordem (horária ou
anti-horária). O script fecha o polígono, cria uma triangulação simples do
interior e atribui todas as células ao material soil1. O perfil superior é
inferido automaticamente para preencher a secção de superfície exigida pelo
modelo Slide2, sem pedir índices ao utilizador.

Execução interativa com janela para escolher um modelo .slim salvo no Slide2:
    python slide2_editar_modelo.py

Execução com argumentos:
    python slide2_editar_modelo.py modelo_vazio.slim \
        --pontos "0,-15;43,-15;43,6;23,6;20,0;0,0" \
        --coesao 18 --phi 22 --gamma 20

Não utiliza bibliotecas externas. O formato .sli interno é editado diretamente.
Use como base um modelo salvo pelo Slide2 que já contenha uma External
Boundary, mesmo que seja mínima; um .slim totalmente vazio não serve como
molde editável. Este formato não é uma API documentada; valide sempre o
ficheiro resultante no Slide2 antes de o utilizar numa análise de engenharia.
"""
from __future__ import annotations
import argparse
import copy
import math
import re
import sys
import zipfile
from pathlib import Path

EPS = 1e-10


def fmt(value: float) -> str:
    return f"{value:.12g}"


def escolher_arquivo() -> Path:
    """Abre a janela do sistema para selecionar o modelo .slim de entrada."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise RuntimeError("Não foi possível abrir a janela de ficheiros; informe o caminho do .slim como argumento.") from exc
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        selected = filedialog.askopenfilename(
            title="Selecione um modelo Slide2 com External Boundary para usar como base",
            filetypes=[("Modelos Slide2 (*.slim)", "*.slim"), ("Todos os arquivos", "*.*")],
        )
    finally:
        root.destroy()
    if not selected:
        raise RuntimeError("Nenhum arquivo foi selecionado. Operação cancelada.")
    return Path(selected)


def parse_points(text: str) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for item in text.split(";"):
        fields = item.strip().split(",")
        if len(fields) != 2:
            raise ValueError(f"Coordenada inválida {item!r}; use x,y;x,y;... (ex.: 0,-15;43,-15;43,6;0,6).")
        x, y = map(float, fields)
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError("As coordenadas devem ser números finitos.")
        pts.append((x, y))
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) <= EPS:
        pts.pop()  # o fecho é feito no arquivo Slide2, não duplicando o primeiro ponto
    if len(pts) < 3:
        raise ValueError("A boundary precisa de pelo menos três vértices distintos.")
    for i in range(len(pts)):
        if math.dist(pts[i], pts[(i + 1) % len(pts)]) <= EPS:
            raise ValueError("Há vértices consecutivos repetidos ou um segmento de comprimento zero.")
    if len(set(pts)) != len(pts):
        raise ValueError("A lista contém vértices duplicados; forneça cada vértice uma única vez.")
    return pts


def area2(poly: list[tuple[float, float]]) -> float:
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))


def normalize_polygon(poly: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Canonicalize vertex order to counter-clockwise, starting bottom-left."""
    points = list(poly)
    if area2(points) < 0:
        points.reverse()
    start = min(range(len(points)), key=lambda i: (points[i][1], points[i][0]))
    return points[start:] + points[:start]


def orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a, b, p) -> bool:
    return min(a[0], b[0]) - EPS <= p[0] <= max(a[0], b[0]) + EPS and min(a[1], b[1]) - EPS <= p[1] <= max(a[1], b[1]) + EPS


def segments_intersect(a, b, c, d) -> bool:
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if ((o1 > EPS and o2 < -EPS) or (o1 < -EPS and o2 > EPS)) and ((o3 > EPS and o4 < -EPS) or (o3 < -EPS and o4 > EPS)):
        return True
    return (abs(o1) <= EPS and on_segment(a, b, c)) or (abs(o2) <= EPS and on_segment(a, b, d)) or (abs(o3) <= EPS and on_segment(c, d, a)) or (abs(o4) <= EPS and on_segment(c, d, b))


def validate_simple_polygon(poly: list[tuple[float, float]]) -> None:
    if abs(area2(poly)) <= EPS:
        raise ValueError("A boundary tem área nula ou vértices colineares; confira as coordenadas.")
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        for j in range(i + 1, n):
            # Arestas vizinhas partilham um vértice e isso é esperado.
            if j == i or j == (i + 1) % n or (j + 1) % n == i:
                continue
            c, d = poly[j], poly[(j + 1) % n]
            if segments_intersect(a, b, c, d):
                raise ValueError(f"A boundary cruza-se ou toca-se entre os segmentos {i + 1} e {j + 1}; use um polígono simples sem auto-interseções.")


def point_in_triangle(p, a, b, c, sign: float) -> bool:
    return sign * orient(a, b, p) >= -EPS and sign * orient(b, c, p) >= -EPS and sign * orient(c, a, p) >= -EPS


def triangulate(poly: list[tuple[float, float]]) -> list[tuple[int, int, int]]:
    """Ear clipping para polígono simples; devolve índices de vértices 1-based."""
    validate_simple_polygon(poly)
    sign = 1.0 if area2(poly) > 0 else -1.0
    remaining = list(range(len(poly)))
    triangles: list[tuple[int, int, int]] = []
    attempts = 0
    while len(remaining) > 3:
        clipped = False
        for k, curr in enumerate(remaining):
            prev = remaining[k - 1]
            nxt = remaining[(k + 1) % len(remaining)]
            a, b, c = poly[prev], poly[curr], poly[nxt]
            if sign * orient(a, b, c) <= EPS:
                continue
            if any(point_in_triangle(poly[q], a, b, c, sign) for q in remaining if q not in (prev, curr, nxt)):
                continue
            triangles.append((prev + 1, curr + 1, nxt + 1))
            del remaining[k]
            clipped = True
            break
        attempts += 1
        if not clipped or attempts > len(poly) * len(poly):
            raise ValueError("Não consegui triangular a boundary. Confira se há pontos colineares, cruzamentos ou vértices em ordem incorreta.")
    triangles.append(tuple(i + 1 for i in remaining))
    return triangles


def infer_slope_profile(poly: list[tuple[float, float]]) -> list[int]:
    """Infer the upper, x-monotone boundary chain from leftmost to rightmost."""
    n = len(poly)
    min_x = min(x for x, _ in poly)
    max_x = max(x for x, _ in poly)
    left = [i for i, (x, _) in enumerate(poly) if abs(x - min_x) <= EPS]
    right = [i for i, (x, _) in enumerate(poly) if abs(x - max_x) <= EPS]
    candidates = []
    for i in left:
        for j in right:
            if i == j:
                continue
            for direction in (1, -1):
                ids = [i]
                k = i
                while k != j and len(ids) <= n:
                    k = (k + direction) % n
                    ids.append(k)
                xs = [poly[q][0] for q in ids]
                if all(xs[t + 1] >= xs[t] - EPS for t in range(len(xs) - 1)):
                    ys = [poly[q][1] for q in ids]
                    candidates.append((sum(ys) / len(ys), len(ids), ids))
    if not candidates:
        raise ValueError("Não consegui inferir automaticamente o perfil superior. Reordene o contorno ou use um polígono com uma superfície superior monotónica em X.")
    # Prefer the upper chain, then the shorter of equally high alternatives.
    candidates.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    return [i + 1 for i in candidates[0][2]]


def replace_section(text: str, name: str, replacement: str, next_section: str) -> str:
    pattern = rf"(?ms)^{re.escape(name)}:\n.*?(?=^{re.escape(next_section)}:|\Z)"
    updated, count = re.subn(pattern, replacement.rstrip() + "\n", text, count=1)
    if count != 1:
        raise ValueError(f"Não encontrei a secção esperada {name!r} antes de {next_section!r}.")
    return updated


def update_sli(text: str, points: list[tuple[float, float]],
               cohesion: float, phi: float, gamma: float, material: str) -> str:
    if cohesion < 0 or not 0 <= phi < 90 or gamma <= 0:
        raise ValueError("Use c >= 0, 0 <= phi < 90 graus e gamma > 0.")
    triangles = triangulate(points)
    n = len(points)
    slope_ids = infer_slope_profile(points)

    mat_pattern = rf"(?m)^(\s*{re.escape(material)}\s*=\s*type:\s*\d+\s+water:\s*\d+\s+wtable:\s*\d+\s+c:)\s*[^\s]+(\s+phi:)\s*[^\s]+(\s+uw:)\s*[^\s]+(.*)$"
    text, count = re.subn(mat_pattern, lambda m: f"{m.group(1)} {fmt(cohesion)}{m.group(2)} {fmt(phi)}{m.group(3)} {fmt(gamma)}{m.group(4)}", text, count=1)
    if count != 1:
        raise ValueError(f"Não foi possível atualizar o material {material!r} no .sli.")

    vertices_text = "vertices:\n" + "\n".join(f"  {i} x: {fmt(x)}  y: {fmt(y)}" for i, (x, y) in enumerate(points, 1))
    text = replace_section(text, "vertices", vertices_text, "cells")
    cells_text = "cells:\n" + "\n".join(f"  {i}  vertices: [{a},{b},{c}] material: {material}" for i, (a, b, c) in enumerate(triangles, 1))
    text = replace_section(text, "cells", cells_text, "anchors")
    slope_text = "slope:\n  1  vertices: [" + ",".join(map(str, slope_ids)) + "]"
    text = replace_section(text, "slope", slope_text, "exterior")
    exterior_text = "exterior:\n  1  vertices: [" + ",".join(str(i) for i in range(1, n + 1)) + "]"
    text = replace_section(text, "exterior", exterior_text, "forces")

    slope_start, slope_end = points[slope_ids[0] - 1], points[slope_ids[-1] - 1]
    limits_pattern = r"(?m)^(\s*x1:)\s*[^\s]+(\s+y1:)\s*[^\s]+(\s+x2:)\s*[^\s]+(\s+y2:)\s*[^\s]+"
    text, count = re.subn(limits_pattern, lambda m: f"{m.group(1)} {fmt(slope_start[0])}{m.group(2)} {fmt(slope_start[1])}{m.group(3)} {fmt(slope_end[0])}{m.group(4)} {fmt(slope_end[1])}", text, count=1)
    if count != 1:
        raise ValueError("Não encontrei os limites de pesquisa do perfil no modelo-base.")

    geom_header = (
        "geometry info:\n"
        "#0:External boundary  1:Excavation  2:Joint  3:Material  4:Stage\n"
        "#  Material Type    End Flag        Vertex (x,y)        Disc (x,y)       A.B.I    Visible\n"
        "# ----------------------------------------------------------------------------------------------"
    )
    geom_rows = [f"         0                {1 if i == n else 0}        {fmt(x)},{fmt(y)}           0              0          1" for i, (x, y) in enumerate(points, 1)]
    geom = geom_header + "\n" + "\n".join(geom_rows) + "\n"
    text, count = re.subn(r"(?ms)^geometry info:\n.*\Z", geom, text, count=1)
    if count != 1:
        raise ValueError("Não encontrei a secção geometry info no .sli.")
    return text


def interactive_points() -> list[tuple[float, float]]:
    while True:
        try:
            count = int(input("Quantos vértices tem o contorno externo? "))
            if count < 3:
                print("Informe no mínimo 3 vértices.")
                continue
            break
        except ValueError:
            print("Digite um número inteiro.")
    pts = []
    for i in range(1, count + 1):
        while True:
            raw = input(f"Coordenada do vértice {i} (x,y): ").strip()
            try:
                p = parse_points(raw)
                if len(p) != 1:
                    raise ValueError("Digite apenas um par x,y.")
                pts.extend(p)
                break
            except ValueError as exc:
                # parse_points requer 3 pontos; um par isolado é lido aqui diretamente.
                fields = raw.split(",")
                try:
                    if len(fields) != 2:
                        raise ValueError
                    x, y = map(float, fields)
                    if not (math.isfinite(x) and math.isfinite(y)):
                        raise ValueError
                    pts.append((x, y))
                    break
                except ValueError:
                    print(f"Coordenada inválida: {exc if len(fields) != 2 else 'use valores numéricos finitos no formato x,y'}")
    return parse_points(";".join(f"{x},{y}" for x, y in pts))


def main() -> int:
    parser = argparse.ArgumentParser(description="Cria geometry/células Slide2 a partir de uma boundary poligonal.")
    parser.add_argument("arquivo", type=Path, nargs="?", help="Modelo-base .slim; se omitido, abre janela para escolher")
    parser.add_argument("--pontos", help='Todos os vértices da boundary, em ordem, como "x,y;x,y;x,y"')
    parser.add_argument("--coesao", type=float, help="Coesão c nas unidades de tensão do modelo")
    parser.add_argument("--phi", type=float, help="Ângulo de atrito phi em graus")
    parser.add_argument("--gamma", type=float, help="Peso específico gamma nas unidades do modelo")
    parser.add_argument("--material", default="soil1", help="Material único da região, por padrão soil1")
    parser.add_argument("--saida", type=Path, help="Caminho do novo .slim; nunca sobrescreve o original")
    args = parser.parse_args()

    try:
        source = (args.arquivo if args.arquivo is not None else escolher_arquivo()).expanduser().resolve()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not source.is_file() or source.suffix.lower() != ".slim":
        parser.error(f"Selecione um arquivo .slim existente: {source}")

    try:
        points = parse_points(args.pontos) if args.pontos else interactive_points()
        points = normalize_polygon(points)
        validate_simple_polygon(points)
        slope_ids = infer_slope_profile(points)
        cohesion = args.coesao if args.coesao is not None else float(input("Coesão c: "))
        phi = args.phi if args.phi is not None else float(input("Ângulo de atrito phi (graus): "))
        gamma = args.gamma if args.gamma is not None else float(input("Peso específico gamma: "))
        if args.saida is not None:
            destination = args.saida.expanduser().resolve()
            if destination == source or destination.exists():
                raise ValueError(f"A saída já existe ou coincide com o original; escolha outro caminho: {destination}")
        else:
            destination = source.with_name(source.stem + "_editado.slim").resolve()
            suffix = 2
            while destination == source or destination.exists():
                destination = source.with_name(f"{source.stem}_editado_{suffix}.slim").resolve()
                suffix += 1

        with zipfile.ZipFile(source, "r") as zin:
            bad = zin.testzip()
            if bad:
                raise ValueError(f"Falha de integridade no membro ZIP {bad!r}.")
            members = [(info, zin.read(info.filename)) for info in zin.infolist()]
        sli_indices = [i for i, (info, _) in enumerate(members) if info.filename.lower().endswith(".sli")]
        if len(sli_indices) != 1:
            raise ValueError(f"Esperava exatamente um arquivo .sli dentro do pacote; encontrei {len(sli_indices)}.")
        idx = sli_indices[0]
        original_sli = members[idx][1]
        newline = "\r\n" if b"\r\n" in original_sli else "\n"
        sli_text = original_sli.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        modified = update_sli(sli_text, points, cohesion, phi, gamma, args.material)
        members[idx] = (members[idx][0], modified.replace("\n", newline).encode("utf-8"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w") as zout:
            for info, data in members:
                out_info = copy.copy(info)
                inner_path = Path(info.filename)
                if inner_path.suffix.lower() in {".sli", ".slv", ".sltm"}:
                    out_info.filename = str(inner_path.with_name(destination.stem + inner_path.suffix))
                zout.writestr(out_info, data)
        with zipfile.ZipFile(destination, "r") as check:
            bad = check.testzip()
            if bad:
                raise ValueError(f"Falha ao verificar o ZIP de saída: {bad!r}.")
        print(f"Novo modelo criado: {destination}")
        print(f"Vértices da boundary: {len(points)}; células de solo: {len(triangulate(points))}; perfil superior inferido: {slope_ids}")
        print(f"Material {args.material}: c={cohesion:g}, phi={phi:g} graus, gamma={gamma:g}")
        print("O original não foi alterado. Abra o novo arquivo no Slide2 e valide a geometria antes de analisar.")
        return 0
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
