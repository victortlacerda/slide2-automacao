# 03 - Planilha para `.slim` (planejado)

Vai ler a planilha gerada pelo módulo 02 e criar **um `.slim` por seção ativa**, com várias
camadas de solo, a partir do molde `modulos/01_modelo_basico/modelo_base/vazio.slim`.

## Divisão de responsabilidades

- **Planilha** (dados): coordenadas das regiões, materiais e associação região → material.
- **Terminal** (decisões de análise, sempre perguntadas ao usuário):
  - direção da ruptura **por seção** (com a opção "mesma para todas"), mostrando o perfil;
  - métodos de equilíbrio limite (Bishop, Fellenius, Janbu, Spencer, M-P...);
  - tipo de superfície (circular ou não circular);
  - busca: grelha manual, Auto Refine ou AutoGrid, conforme o usuário escolher.
  O script **não escolhe** a direção nem a "melhor" busca.
- **JSON**: as respostas ficam gravadas ao lado dos modelos, para repetir a rodada e registrar
  no memorial o que foi usado.

## O que falta para começar

Amostras salvas a partir do `vazio.slim`, cada uma com **uma única mudança**, para mapear o
formato do arquivo (lista completa em [`docs/roadmap.md`](../../docs/roadmap.md)):

1. duas camadas (fronteira interna + 2 materiais diferentes);
2. só Bishop, só Fellenius (e Bishop + Fellenius);
3. direção esquerda → direita.
