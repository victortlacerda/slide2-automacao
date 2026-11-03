# O que se sabe do formato do Slide2

Levantado a partir do `vazio.slim` (Slide2, `version: 6.020`). O formato não é documentado pela
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
| `model description` | Parâmetros globais. `direction: right to left` = sentido da ruptura. `methods: 6` = métodos ativos (**codificação desconhecida**). `units: metric`, `nummaterials: 20`, `numanchors: 20`. |
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
