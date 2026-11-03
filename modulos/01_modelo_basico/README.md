# 01 - Modelo básico: boundary e um material

`slide2_editar_modelo.py` cria um novo `.slim` a partir de um modelo-base, com:

- **contorno externo** (external boundary) a partir dos vértices informados;
- **um material** (`soil1` por padrão) com c, φ e γ;
- perfil superior (superfície do talude) e limites de busca inferidos da geometria.

Foi o primeiro teste do projeto: provar que é possível montar um modelo editando o arquivo do
Slide2 diretamente. Não usa bibliotecas externas.

## Uso

```bash
# interativo: abre janela para escolher o modelo-base e pergunta os vértices no terminal
python slide2_editar_modelo.py

# com argumentos
python slide2_editar_modelo.py modelo_base/vazio.slim \
    --pontos "0,-15;43,-15;43,6;23,6;20,0;0,0" --coesao 18 --phi 22 --gamma 20
```

A saída é `<modelo>_editado.slim` ao lado do original, que nunca é sobrescrito.

## Modelo-base

`modelo_base/vazio.slim` é um modelo salvo pelo Slide2 contendo apenas um quadrado 1 × 1.
Um modelo totalmente vazio não serve: o arquivo editado deixa de abrir no Slide2. O molde
traz todos os parâmetros globais, 20 slots de material e 20 slots de suporte.

## O que o script altera no `.sli`

`vertices`, `cells`, `slope`, `exterior`, `slope limits`, `geometry info` e a linha do material
em `material types`.

## Limitações conhecidas

- **Direção da ruptura não é alterada:** fica a do molde (`direction: right to left`). Para um
  talude com a face voltada para a direita, ajuste no Slide2.
- **Um único material:** todas as células recebem o mesmo solo; não há camadas.
- **Suportes, água, cargas e grelha de busca** não são tocados; o molde vem sem eles.
- O perfil superior é inferido como a cadeia mais alta e monotônica em X entre o vértice
  mais à esquerda e o mais à direita; geometrias com reentrâncias podem falhar.
- As coordenadas são gravadas em formato curto (`0,-15`), diferente do formato longo que o
  Slide2 grava (`1.00000000000000,0.000000000000000`); confira sempre no Slide2.

Essas limitações serão tratadas no módulo 03, que generaliza este script para várias
camadas a partir da planilha.
