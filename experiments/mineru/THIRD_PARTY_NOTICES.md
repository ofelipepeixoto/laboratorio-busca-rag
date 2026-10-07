# Atribuição e limites de licença

O runner, controles, gerador e fixtures deste diretório são trabalho original
de Carlos Felipe / Help Mídias, feito com assistência de IA. Aplica-se a licença
MIT dos controles Radar em `../../licenses/RADAR-CONTROLS-MIT.txt`.
Isso não altera licenças do restante do repositório ou de dependências.

MinerU pertence ao OpenDataLab e seus contribuidores. Snapshot:
https://github.com/opendatalab/MinerU/tree/ed50cc15bc2c9bfb00520dadfe61979866e62236
Licença: `licenses/MinerU-LICENSE.md`, conservada sem modificações, junto à
Apache-2.0 referenciada (`licenses/Apache-2.0.txt`).

Os arquivos `patches/0001-*`, `0002-*` e `0003-*` contêm alterações derivadas ao
MinerU, produzidas na auditoria de 07/10/2026. Mantêm o copyright e os termos do
upstream. Modificações: consentimento explícito de telemetria, upload por stream
com teto e rejeição de API key explicitamente vazia/com espaços. Não foram
incorporadas ao upstream e não representam hardening completo. Nenhum nome,
marca ou autoria do motor é reivindicado pelo Radar.

DocVortex 0.5.11 é dependência MIT; cópia de sua licença instalada está em
`licenses/DocVortex-LICENSE.md`. pypdf, PDFium/pypdfium2, libseccomp e demais
dependências conservam seus avisos nas próprias distribuições. Esta PR não
redistribui wheels, código integral upstream, fontes tipográficas ou pesos.

O scan fictício foi rasterizado a partir do PDF autoral com PDFium; Helvetica
é referenciada como fonte padrão PDF e nenhum arquivo de fonte foi incluído.

A licença MinerU é personalizada, com condições adicionais; o nome do projeto
na interface/readme não elimina outras obrigações. O estudo local não é serviço
comercial homologado. Pendências de proveniência/licença de pesos, binários
`mineru-llama-cpp` e itens vendorizados permanecem gates de futura adoção.
