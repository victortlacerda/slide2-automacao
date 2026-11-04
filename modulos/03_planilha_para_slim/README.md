# 03 - Planilha para `.slim`

`planilha_para_slim.py` lê a planilha gerada pelo módulo 02 e cria **um modelo `.slim` por seção
ativa**, a partir do molde `modulos/01_modelo_basico/modelo_base/vazio.slim`, com:

- **várias camadas de solo**, cada região com o seu material;
- **interfaces de material** e **contorno externo** montados a partir das regiões;
- **superfície do terreno** e **limites de busca** (do ponto mais alto da borda esquerda ao da direita);
- **nível d'água** (aba NA), recortado no contorno e prolongado na horizontal se não cobrir a seção;
- **cargas** (aba Cargas): distribuídas verticais e em linha com qualquer ângulo, assentadas sobre o terreno;
- **direção da ruptura** e **métodos de equilíbrio limite**, perguntados no terminal.

## Uso

```bash
python planilha_para_slim.py                                   # interativo
python planilha_para_slim.py secoes.xlsx --direcao esq-dir --metodos 1,9
python planilha_para_slim.py --config secoes_modelos/respostas.json   # repete uma rodada
```

Saída: pasta `<planilha>_modelos/` com um `.slim` e uma prévia `.png` por seção, mais
`respostas.json`. Nada é sobrescrito.

## Perguntas no terminal

| Pergunta | Opções |
|---|---|
| **Mesma direção para todas as seções?** | `s`: uma resposta para todas. `n`: pergunta seção por seção. Direção: `1` = direita → esquerda, `2` = esquerda → direita. Nunca é adivinhada. |
| **Quais métodos?** | Números na ordem da janela do Slide2: 1 Bishop, 2 Corps #1, 3 Corps #2, 4 GLE/M-P, 5 Janbu simplificado, 6 Janbu corrigido, 7 Lowe-Karafiath, 8 Fellenius, 9 Spencer. Ex.: `1,9`. |

## O que vem da planilha

| Aba | Uso |
|---|---|
| Materiais | γ, c', φ' e cor (opcional) de cada material. A ordem das linhas define `soil1`, `soil2`... |
| Regioes | Material de cada região. Região sem material impede a seção de ser gerada. |
| Vertices | Coordenadas das regiões (não editar). |
| Secoes | `Ativa = n` pula a seção. **Cota real do ponto mais alto** desloca a seção em Y. |
| NA | Pontos do NA da esquerda para a direita. `Origem = CAD` acompanha o desenho; digitado (`planilha`) é cota real. |
| Cargas | `distribuida`: X início, X fim, kPa (só vertical nesta versão). `linha`: X, kN/m e ângulo (270 = para baixo). |

## Validação

Os modelos gerados foram abertos no Slide 6.0: camadas, lente, NA, cargas (inclusive atravessando
o talude), métodos e direção aparecem como na prévia.

O teste `testes/test_planilha_para_slim.py` reconstrói a amostra **a02**, salva pelo próprio
Slide2, a partir das mesmas entradas, e confere bloco a bloco: vértices (mesma numeração),
contorno, terreno, NA, cargas, materiais, métodos, direção, limites de busca e interface.

## Limitações desta versão

- **Busca da superfície não é gravada** (grelha, Auto Refine, AutoGrid): defina no Slide2 antes de
  calcular. Entra na fase 4, com as amostras da issue #9.
- **Carga distribuída só vertical e uniforme.** Quando atravessa uma quebra do terreno, vira trechos
  (o Slide mostra cada trecho com o seu rótulo).
- **γ saturado** ainda não é gravado.
