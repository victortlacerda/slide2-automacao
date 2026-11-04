# 03 - Planilha para `.slim`

`planilha_para_slim.py` lê a planilha gerada pelo módulo 02 e cria **um modelo `.slim` por seção
ativa**, a partir do molde `modulos/01_modelo_basico/modelo_base/vazio.slim`, com:

- **várias camadas de solo**, cada região com o seu material;
- **interfaces de material** e **contorno externo** montados a partir das regiões;
- **superfície do terreno** e **limites de busca** (do ponto mais alto da borda esquerda ao da direita);
- **nível d'água** (aba NA), recortado no contorno e prolongado na horizontal se não cobrir a seção;
- **cargas** (aba Cargas): distribuídas verticais e em linha com qualquer ângulo, assentadas sobre o terreno;
- **direção da ruptura**, **métodos de equilíbrio limite** e **busca da superfície**, perguntados no terminal.

## Uso

```bash
python planilha_para_slim.py                                   # interativo
python planilha_para_slim.py secoes.xlsx --direcao esq-dir --metodos 1,9 --superficie circular --busca autorefine
python planilha_para_slim.py secoes.xlsx --superficie circular --busca grid --grelha planilha
python planilha_para_slim.py --config secoes_modelos/respostas.json   # repete uma rodada
```

Saída: pasta `<planilha>_modelos/` com um `.slim` e uma prévia `.png` por seção, mais
`respostas.json`. Nada é sobrescrito.

## Perguntas no terminal

| Pergunta | Opções |
|---|---|
| **Mesma direção para todas as seções?** | `s`: uma resposta para todas. `n`: pergunta seção por seção. Direção: `1` = direita → esquerda, `2` = esquerda → direita. Nunca é adivinhada. |
| **Quais métodos?** | Números na ordem da janela do Slide2: 1 Bishop, 2 Corps #1, 3 Corps #2, 4 GLE/M-P, 5 Janbu simplificado, 6 Janbu corrigido, 7 Lowe-Karafiath, 8 Fellenius, 9 Spencer. Ex.: `1,9`. |
| **Tipo de superfície** | `1` = circular, `2` = não circular. |
| **Qual busca?** | Circular: Grid Search, Slope Search, Auto Refine. Não circular: Block Search, Path Search, Simulated Annealing, Auto Refine. |
| **Grelha** (só Grid Search) | `1` = da aba **Grelha** (X1, Y1, X2, Y2, nx, ny por seção). `2` = automática, com a regra própria abaixo. |

O script não escolhe a busca: ela é sempre do usuário.

### Grelha automática (regra própria, não é o AutoGrid do Slide2)

O AutoGrid do Slide2 não grava marcador no arquivo e a sua regra não é documentada, por isso não é
imitado. A opção automática usa uma regra simples e declarada: H = desnível do terreno; face =
trechos com inclinação acima de 10 %. Centros de 1,5 H **para o lado do pé** (segundo a direção
escolhida) até 0,5 H para o lado da crista, e do topo até topo + 2 H, com 20 × 20 intervalos.
O módulo 04 avisa quando o mínimo cai na borda da grelha; nesse caso amplie a grelha na aba Grelha.

## O que vem da planilha

| Aba | Uso |
|---|---|
| Materiais | γ, c', φ' e cor (opcional) de cada material. A ordem das linhas define `soil1`, `soil2`... |
| Regioes | Material de cada região. Região sem material impede a seção de ser gerada. |
| Vertices | Coordenadas das regiões (não editar). |
| Secoes | `Ativa = n` pula a seção. **Cota real do ponto mais alto** desloca a seção em Y. |
| NA | Pontos do NA da esquerda para a direita. `Origem = CAD` acompanha o desenho; digitado (`planilha`) é cota real. |
| Grelha | Só para Grid Search com grelha da planilha: cantos X1, Y1, X2, Y2 (cota real) e nx, ny. |
| Cargas | `distribuida`: X início, X fim, kPa (só vertical nesta versão). `linha`: X, kN/m e ângulo (270 = para baixo). |

## Validação

Os modelos gerados foram abertos no Slide 6.0: camadas, lente, NA, cargas (inclusive atravessando
o talude), métodos e direção aparecem como na prévia.

O teste `testes/test_planilha_para_slim.py` reconstrói a amostra **a02**, salva pelo próprio
Slide2, a partir das mesmas entradas, e confere bloco a bloco: vértices (mesma numeração),
contorno, terreno, NA, cargas, materiais, métodos, direção, limites de busca e interface.

## Limitações desta versão

- **Block Search** precisa de objetos de busca (janelas, linhas) que o script não grava: defina-os no
  Slide2 antes de calcular.
- Os parâmetros de cada busca (nº de superfícies, iterações) ficam nos valores padrão do molde.
- **Carga distribuída só vertical e uniforme.** Quando atravessa uma quebra do terreno, vira trechos
  (o Slide mostra cada trecho com o seu rótulo).
- **γ saturado** ainda não é gravado.
