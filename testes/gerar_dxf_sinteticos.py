"""Geradores de DXF sintéticos para os testes do módulo 02.

Todos usam o perfil do guia da aula: terreno (0,0)-(20,0)-(23,6)-(43,6), base em -15,
largura 43 m -> área total 774 m².
"""
import ezdxf

TERRENO = [(0, 0), (20, 0), (23, 6), (43, 6)]


def y_interface2(x):
    """Interface inclinada de (0,-8) a (43,-10)."""
    return -8 - 2 * (x / 43)


def tres_camadas(caminho):
    """Seção 1 em LINEs soltas (x = 0), seção 2 em polilinhas fechadas com vértice em T (x = 100),
    seção 3 com polilinha aberta fechada pela camada de cima (x = 200)."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    L = {"dxfattribs": {"layer": "SEC_LINHAS"}}
    P = {"dxfattribs": {"layer": "SEC_POLI"}}
    for a, b in zip(TERRENO, TERRENO[1:]):
        msp.add_line(a, b, **L)
    for a, b in [((0, 0), (0, -15)), ((43, 6), (43, -15)), ((0, -15), (43, -15)),
                 ((0, -3), (43, -3)), ((0, -8), (43, y_interface2(43)))]:
        msp.add_line(a, b, **L)
    msp.add_text("SECAO 1", dxfattribs={"layer": "SEC_LINHAS", "height": 1.0}).set_placement((0, 9))
    dx = 100
    msp.add_lwpolyline([(x + dx, y) for x, y in TERRENO] + [(43 + dx, -3), (dx, -3)], close=True, **P)
    msp.add_lwpolyline([(dx, -3), (43 + dx, -3), (43 + dx, y_interface2(43)), (20 + dx, y_interface2(20)), (dx, -8)],
                       close=True, **P)
    msp.add_lwpolyline([(dx, -8), (43 + dx, y_interface2(43)), (43 + dx, -15), (dx, -15)], close=True, **P)
    dx = 200
    msp.add_lwpolyline([(x + dx, y) for x, y in TERRENO] + [(43 + dx, -3), (dx, -3)], close=True, **P)
    msp.add_lwpolyline([(dx, -3), (dx, -15), (43 + dx, -15), (43 + dx, -3)], **P)
    doc.saveas(caminho)


def casos_de_desenho(caminho):
    """A: falha de 0,4 mm (x=0); B: falha de 10 cm (x=100); C: lente/furo (x=200); D: fundo em arco (x=300)."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    for dx, ponta in ((0, -3.0004), (100, -3.1)):
        msp.add_lwpolyline([(x + dx, y) for x, y in TERRENO] + [(43 + dx, -3), (dx, -3)], close=True)
        msp.add_line((dx, -3), (dx, -15))
        msp.add_line((dx, -15), (43 + dx, -15))
        msp.add_line((43 + dx, -15), (43 + dx, ponta))
    dx = 200
    msp.add_lwpolyline([(x + dx, y) for x, y in TERRENO] + [(43 + dx, -15), (dx, -15)], close=True)
    msp.add_lwpolyline([(10 + dx, -8), (30 + dx, -8), (30 + dx, -5), (10 + dx, -5)], close=True)
    dx = 300
    pts = [(x + dx, y, 0, 0, 0) for x, y in TERRENO] + [(43 + dx, -15, 0, 0, 0.2), (dx, -15, 0, 0, 0)]
    msp.add_lwpolyline(pts, format="xyseb", close=True)
    doc.saveas(caminho)


if __name__ == "__main__":
    import sys
    tres_camadas(sys.argv[1] if len(sys.argv) > 1 else "tres_camadas.dxf")
    casos_de_desenho(sys.argv[2] if len(sys.argv) > 2 else "casos_de_desenho.dxf")
