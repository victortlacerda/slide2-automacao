# 04 - Cálculo em lote

`calcular_lote.py` calcula uma pasta de modelos `.slim` com o motor do próprio Slide2
(`aslidew.exe`) e junta os resultados numa planilha.

Para cada modelo:

1. roda `aslidew.exe "modelo.slim"`; o resultado fica gravado **dentro** do `.slim` (abre no Slide2
   já calculado);
2. lê o **FS mínimo global de cada método**, o centro e o raio do círculo crítico, os pontos de
   entrada e saída e as superfícies válidas e inválidas;
3. confere e avisa:
   - centro crítico na **borda da grelha** (amplie ou desloque a grelha);
   - superfície tocando o **limite de busca** ou o **fundo do modelo**;
   - FS inválido e, se informado, FS abaixo do **FS-alvo**;
4. grava `resultados.xlsx` (abas Resumo, Figuras e Origem) e `resultados_figuras/<seção>.png` com
   as camadas, o NA, a grelha e a superfície crítica.

## Uso

```bash
python calcular_lote.py                                    # escolhe a pasta numa janela
python calcular_lote.py pasta_dos_modelos --aslide "C:\Program Files\Rocscience\Slide\aslidew.exe" --fs-alvo 1.5
python calcular_lote.py --somente-ler pasta_dos_modelos    # só lê resultados já calculados
```

| Opção | Uso |
|---|---|
| `--aslide` | Caminho do `aslidew.exe` (na pasta do Slide2). Perguntado na primeira vez e salvo em `~/.slide2_automacao.json`. |
| `--fs-alvo` | FS mínimo exigido. Sem ele, o script só reporta. |
| `--somente-ler` | Não calcula; lê os modelos já calculados (pela interface ou por uma rodada anterior). |
| `--timeout` | Tempo máximo por modelo, em segundos. |
| `--saida` | Caminho da planilha de resultados. |

**Atenção:** o `aslidew.exe` devolve código de saída 2 mesmo quando calcula. O script confere o
resultado pelo membro `.s01` gravado no `.slim`, não pelo código.

## Validação

- A mesma amostra calculada pela interface e pela linha de comando dá o mesmo FS (Bishop 0,316616;
  Janbu 0,297976).
- Teste no Slide 6.0 do usuário: 12 modelos (4 seções × Auto Refine, grelha v0.3 e grelha v0.4)
  calculados em 2 a 3 s cada. Com a regra de grelha antiga, os 4 mínimos caíram na borda e o
  aviso apareceu; com a regra nova, nenhum.
- `testes/test_calcular_lote.py` lê um resultado real do Slide e usa um `aslidew` falso para testar
  o lote fora do Windows.

## Limitações desta versão

- Os avisos de borda valem para Grid Search; nas outras buscas só há o aviso de limite e de fundo.
- Superfícies não circulares são desenhadas pelas fatias; não há centro nem raio.
- Uma rodada por pasta; cenários (NA alto/baixo, com e sem carga) entram na fase 5.
