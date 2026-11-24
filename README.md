# Automacao - Agenda Regulatoria

Pacote para extrair diariamente os dados do Power BI publico da Agenda Regulatoria 2026-2027 e atualizar `agenda_regulatoria.json` no repositorio.

Conteudo:
- `.github/workflows/atualizar_agenda_regulatoria.yml`
- `scripts/update_agenda.py`
- `scripts/agenda_config.json`
- `scripts/query_full.json`
- `scripts/query_temas.json`
- `agenda_regulatoria.json` (base validada a partir do HAR de 24/11/2026)

O workflow executa diariamente as 08:30 no horario de Brasilia (11:30 UTC) e tambem permite execucao manual. Se a consulta retornar uma quantidade anormalmente baixa de iniciativas, o script falha antes de substituir o ultimo JSON valido.
