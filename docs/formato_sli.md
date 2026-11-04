# O que se sabe do formato do Slide2

Levantado a partir do `vazio.slim` (Slide2, `version: 6.020`) e das amostras em
[`amostras_slide2/`](amostras_slide2). O formato não é documentado pela
Rocscience; cada item abaixo deve ser confirmado com amostras salvas pelo próprio programa.

## O pacote `.slim`

Um `.slim` é um **ZIP** com três arquivos de texto de mesmo nome-base:

| Arquivo | Conteúdo |
|---|---|
| `.sli` | o modelo: parâmetros, materiais, geometria, busca |
| `.slv` | opções de visualização |
| `.sltm` | ferramentas de desenho e resumo do projeto (título, autor, data) |

Ao gerar um novo modelo, os três membros são renomeados para o nome do novo arquivo.

## Blocos do `.sli` (em ordem)

| Bloco | Situação |
|---|---|
| `model description` | Parâmetros globais. `direction: right to left` = sentido da ruptura. `methods` = métodos ativos (máscara de bits, ver abaixo). `units: metric`, `nummaterials: 20`, `numanchors: 20`. |
| `material types` | `soilN = type: 0 water: 1 wtable: 0 c: <c> phi: <φ> uw: <γ> hutype: 0 withru: 0`. Editado pelo módulo 01. |
| `design standard array` | Coeficientes parciais (Eurocode 7 DA1/DA2/DA3, BS 8006). |
| `anchor types` | `anchorN = type: 1 fa: 0 sp: 1 cap: 100` (campos de grampo/tirante: **a mapear**). |
| `vertices` | `  i x: <x>  y: <y>` |
| `cells` | triângulos `  i  vertices: [a,b,c] material: soilN` |
| `anchors` | vazio no molde (**formato a mapear**) |
| `water table`, `piezos`, `pore pressures` | vazios (**a mapear**) |
| `slope` | índices dos vértices da superfície do terreno |
| `exterior` | índices dos vértices do contorno externo |
| `forces` | vazio; provável bloco de cargas (**a mapear**) |
| `slope limits` | `x1 y1 x2 y2`: limites de entrada/saída da busca |
| `grids`, `centers`, `surfaces` | vazios (**grelha e superfícies a mapear**) |
| blocos de busca | `grid search`, `block search`, `path search`, `autoslope search`, `cuckoo search`... |
| `back analysis of support` | retroanálise de suporte (`compute: no fs: 2`) |
| `material random vars`, `materials mc correlation` | análise probabilística |
| `material gen. hoek-brown` | parâmetros Hoek-Brown por material |
| `material properties` | cores RGB de materiais e suportes |
| `geometry info` | uma linha por vértice: tipo (0 contorno, 1 escavação, 2 junta, 3 material, 4 estágio), flag de fim, `x,y` |

## Observações práticas

- Um modelo **totalmente vazio** não serve como molde: o arquivo editado não abre. O
  `vazio.slim` tem um quadrado 1 × 1 por isso.
- O nome interno dos materiais é fixo (`soil1`...`soil20`); o nome do usuário fica na planilha.
- Para descobrir o formato de um recurso: salve o `vazio.slim` com **uma única mudança** e
  compare os dois `.sli`.

## Amostra a01: duas camadas, NA, ruptura esquerda → direita, cargas

Arquivo: [`amostras_slide2/a01_duas_camadas_na_esq-dir_cargas.slim`](amostras_slide2/a01_duas_camadas_na_esq-dir_cargas.slim).
Geometria: base −15, talude de (20, 0) a (23, −6), interface em y = −6 de x = 0 a 23; NA em y = −6
de x = 0 a 43; carga distribuída de 100 kPa de x = 0 a 20; carga em linha de 200 kN/m em x = 20.

| Recurso | Como fica no `.sli` | Confirmado |
|---|---|---|
| Direção | `direction: left to right` | sim |
| Materiais | `soil1 = ... c: 10 phi: 28 uw: 18`, `soil2 = ... c: 15 phi: 25 uw: 20` | sim |
| Camadas | `cells` triangulados **por região**, cada triângulo com o seu `material:`; a interface entra em `geometry info` com tipo `3` (vértice inicial com flag 0, final com flag 1) | sim |
| Vértice da interface no contorno | O ponto (0, −6) vira vértice e entra na lista `exterior` | sim |
| NA no material | `wtable: 1` em **todos** os materiais (Water Surface = Water Table) | sim |
| Linha d'água | `water table:` com `vertices: [7,3]`, ou seja, **índices** da lista de vértices | parcial: o NA coincidia com vértices existentes |
| Carga distribuída | em `forces`: `type: 0 x1 y1 x2 y2 angle: 270 load: 100 load2: 100` (angle 270 = vertical para baixo; `load2` = valor no fim, para trapezoidal) + bloco `dist load group` (`orient: 4`, `type: 0` = constante, `params: 1` → 100) | parcial: código de `orient` a confirmar |
| Carga em linha | em `forces`: `type: 1 x1 y1 angle: 270 load: 200` | sim |
| Estatística das cargas | bloco `stats params loads` com uma entrada por carga (`2 0 0 0 is_on: 0`) | sim (valores padrão) |
| Limites de busca | `slope limits` do ponto mais à esquerda ao mais à direita do terreno | sim |

## Amostra a02: NA inclinado e carga em linha inclinada

Arquivo: [`amostras_slide2/a02_na_inclinado_carga_inclinada.slim`](amostras_slide2/a02_na_inclinado_carga_inclinada.slim).
Mesmo modelo da a01, com o NA passando por 10 pontos próprios (descendo da borda esquerda, um
trecho plano em y ≈ −9,9 e subindo até a borda direita) e uma carga em linha de 100 kN/m inclinada.

| Recurso | Como fica no `.sli` | Confirmado |
|---|---|---|
| Pontos do NA | **acrescentados ao fim da lista `vertices`** (8 a 17); não entram em `cells`, `exterior` nem `geometry info` | sim |
| Linha d'água | `water table: vertices: [7,8,...,17,3]`: começa e termina em vértices do contorno (bordas esquerda e direita) | sim |
| Carga em linha inclinada | `type: 1 x1: 28.15 y1: -6 angle: 330 load: 100`; ângulo em graus a partir do eixo +x, anti-horário (270 = para baixo; 330 = para baixo e para a direita, 30° abaixo da horizontal) | sim |
| Orientação da carga distribuída | `orient: 4` = **Vertical** (informado pelo usuário: as cargas da a01 eram verticais para baixo) | sim |
| Estatística das cargas | uma entrada `begin: k end: k num: 1` por carga | sim |

A confirmar no módulo 03:
- O NA começa e termina em vértices que **já existiam** no contorno. Se a borda não tiver um vértice
  nessa cota, o plano é inserir o vértice no contorno, como acontece com a interface de material.
- `dist load group` tem `begin`/`end`: provavelmente uma carga distribuída que atravessa uma quebra do
  terreno vira várias linhas em `forces`, agrupadas por esse intervalo.

## Métodos de equilíbrio limite (amostras em `amostras_slide2/metodos/`)

Geradas a partir da a02, uma por método e uma com todos. `methods` é a **soma** dos valores dos
métodos marcados (máscara de bits):

| Método | Valor |
|---|---|
| Ordinary / Fellenius | 1 |
| Bishop simplificado | 2 |
| Janbu simplificado | 4 |
| Spencer | 8 |
| Corps of Engineers #1 | 16 |
| Corps of Engineers #2 | 32 |
| Lowe-Karafiath | 64 |
| GLE / Morgenstern-Price | 128 |
| Janbu corrigido | 256 |

Exemplos: Bishop + Janbu simplificado = 6 (o `vazio.slim`); todos = 511.
Com GLE/M-P marcado, o arquivo ganha, logo depois de `model description`, o bloco
`side force function:` com `type: half_sine` (função de forças entre fatias padrão).
Nenhuma outra linha muda entre as amostras.

## Origem dos dados no módulo 03 (decisão do usuário)

- **NA:** do CAD (camada própria) **ou** da planilha.
- **Cargas:** só da planilha.

## Confirmado abrindo no Slide2 (módulo 03 v0.2)

- Carga distribuída que atravessa quebras do terreno: um trecho por segmento em `forces`, todos
  num único `dist load group` (o Slide mostra os trechos, cada um com o seu rótulo) (`begin` = primeiro, `end` = último, índices a partir de 0), e uma
  entrada por trecho em `stats params loads`.
- Lente (camada inteiramente dentro de outra): interface de material fechada em `geometry info`
  (tipo 3), repetindo o primeiro vértice no fim.
- Pontos do NA que caem no meio de uma aresta do contorno são inseridos como vértices nessa aresta.

## Empacotamento do `.slim` (importante)

O ZIP precisa ser gravado com **cabeçalhos novos**. Copiar os `ZipInfo` do molde (campos extra,
flags) gera arquivos que o Slide 6.0 recusa com "Parâmetro incorreto". Com cabeçalhos novos,
comprimidos ou não, o arquivo abre. O nome interno dos membros não precisa coincidir com o nome
do arquivo (testado), mas os módulos 01 e 03 gravam iguais.

## Busca da superfície (amostras em `amostras_slide2/busca/`)

Salvas no Slide a partir da a02, uma mudança por vez. Campos em `model description`:

| Escolha na janela Surface Options | `mode` | `circularsearch` | `search` |
|---|---|---|---|
| Circular, Grid Search | 0 | 0 | — |
| Circular, Slope Search | 0 | 1 | — |
| Circular, Auto Refine Search | 0 | 2 | — |
| Não circular, Block Search | 1 | — | 0 |
| Não circular, Path Search | 1 | — | 1 |
| Não circular, Simulated Annealing | 1 | — | 3 |
| Não circular, Auto Refine Search | 1 | — | 4 |

Os parâmetros de cada busca (número de superfícies, iterações...) ficam nos blocos `grid search`,
`block search`, `path search`, `simulated annealing search`, `autoslope search` e outros, que já
existem no molde com os valores padrão.

**Grelhas** (bloco `grids:`), uma linha por grelha:
`  1: x1: 22.4541491543866 y1: -0.235917798684918  x2: 29.870745771933 y2: 7.18067881886146  nx: 20 ny: 20`
(`x1, y1` e `x2, y2` = cantos opostos; `nx, ny` = número de intervalos).

**AutoGrid não grava marcador**: o Slide calcula um retângulo e grava só as coordenadas, igual a
uma grelha manual. A regra de cálculo não está documentada; o módulo 03 não tenta imitá-la e usa
uma regra própria, declarada no README do módulo.

## Resultados do cálculo (amostra em `amostras_slide2/resultados/`)

- O motor de cálculo é o `aslidew.exe` (na pasta do Slide). Funciona pela linha de comando:
  `aslidew.exe "modelo.slim"` grava o resultado **dentro** do `.slim` (membro `.s01`);
  `aslidew.exe "modelo.sli"` grava `modelo.s01` ao lado. Leva poucos segundos por modelo.
- O código de saída é **2 mesmo quando dá certo**: confirme pelo `.s01`, não pelo código.
- O `.s01` é texto. Blocos marcados por linhas que começam com `*`:
  - `* Analysis names`: métodos calculados, um por linha.
  - `* Global Minimum FS (xc,yc,r,x1,y1,x2,y2,fs,name)`: **uma linha por método** com centro e raio
    do círculo crítico, pontos de entrada e saída, FS e nome do método.
  - `* Global Minimum Text`: momentos/forças resistentes e atuantes da superfície crítica.
  - `* minimum slice info ... method=<nome>`: fatias da superfície crítica (x, topo, base).
  - `* Factor of Safety Computation Counters`: superfícies válidas e inválidas por método.
  - Antes disso, todas as superfícies de cada centro da grelha (`r, yleft, x1, y1, x2, y2, yright, FS...`);
    FS = -103 marca superfície inválida.
- Conferido: a mesma amostra calculada pela interface e pela linha de comando dá o mesmo FS
  (Bishop 0,316616; Janbu 0,297976).
