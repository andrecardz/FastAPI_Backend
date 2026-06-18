# API Clinica Veterinaria

API REST em FastAPI para gestao de uma clinica veterinaria. O dominio escolhido tem regras de agenda, atendimento, prontuario, vacinacao e historico de estado.

## Como rodar

```bash
docker compose up --build
```

API: `http://localhost:8000`

Swagger: `http://localhost:8000/docs`

Testes dentro do container:

```bash
docker compose run api pytest
```

Rollback das migrations:

```bash
docker compose run api alembic downgrade -1
docker compose run api alembic upgrade head
```

## Entidades

### Owner

Tutor responsavel por um ou mais animais.

| Campo | Tipo | Obrigatorio | Constraints |
| --- | --- | --- | --- |
| id | integer | sim | chave primaria |
| name | string | sim | 2 a 120 caracteres |
| email | string | sim | unico, formato de e-mail |
| phone | string | sim | 8 a 30 caracteres |
| created_at | datetime | sim | gerado pelo sistema |

### Pet

Animal atendido pela clinica.

| Campo | Tipo | Obrigatorio | Constraints |
| --- | --- | --- | --- |
| id | integer | sim | chave primaria |
| owner_id | integer | sim | FK para Owner |
| name | string | sim | 1 a 80 caracteres |
| species | string | sim | 2 a 60 caracteres |
| breed | string | nao | ate 80 caracteres |
| birth_date | date | nao | nao pode estar no futuro |
| weight_kg | decimal | nao | maior que zero |
| status | enum | sim | active, in_treatment, inactive, deceased |

### Veterinarian

Profissional responsavel por consultas.

| Campo | Tipo | Obrigatorio | Constraints |
| --- | --- | --- | --- |
| id | integer | sim | chave primaria |
| name | string | sim | 2 a 120 caracteres |
| crmv | string | sim | unico |
| specialty | string | sim | 2 a 90 caracteres |
| base_consultation_fee | decimal | sim | maior ou igual a zero |
| status | enum | sim | active, on_leave, inactive |

### Appointment

Consulta veterinaria com ciclo de vida.

| Campo | Tipo | Obrigatorio | Constraints |
| --- | --- | --- | --- |
| id | integer | sim | chave primaria |
| pet_id | integer | sim | FK para Pet |
| veterinarian_id | integer | sim | FK para Veterinarian |
| starts_at | datetime | sim | inicio da consulta |
| ends_at | datetime | sim | precisa ser posterior a starts_at |
| reason | string | sim | 5 a 200 caracteres |
| status | enum | sim | scheduled, checked_in, in_progress, completed, canceled |
| total_amount | decimal | sim | calculado pelo sistema |
| created_at | datetime | sim | gerado pelo sistema |

### MedicalRecord

Prontuario clinico gerado durante uma consulta.

| Campo | Tipo | Obrigatorio | Constraints |
| --- | --- | --- | --- |
| id | integer | sim | chave primaria |
| appointment_id | integer | sim | FK unica para Appointment |
| diagnosis | text | sim | minimo 3 caracteres |
| treatment | text | sim | minimo 3 caracteres |
| procedure_cost | decimal | sim | maior ou igual a zero |
| medication_cost | decimal | sim | maior ou igual a zero |
| created_at | datetime | sim | gerado pelo sistema |

### Vaccine

Cadastro de vacinas disponiveis.

| Campo | Tipo | Obrigatorio | Constraints |
| --- | --- | --- | --- |
| id | integer | sim | chave primaria |
| name | string | sim | unico |
| species | string | sim | especie indicada |
| validity_days | integer | sim | maior que zero |
| active | boolean | sim | controla aplicacao |

### VaccinationRecord

Historico de vacina aplicada a um animal.

| Campo | Tipo | Obrigatorio | Constraints |
| --- | --- | --- | --- |
| id | integer | sim | chave primaria |
| pet_id | integer | sim | FK para Pet |
| vaccine_id | integer | sim | FK para Vaccine |
| appointment_id | integer | sim | FK para Appointment |
| applied_at | datetime | sim | data de aplicacao |
| booster_due_at | datetime | sim | posterior a applied_at |
| batch_number | string | sim | 2 a 80 caracteres |

### AuditEvent

Historico tecnico de mudancas relevantes, criado na terceira migration.

| Campo | Tipo | Obrigatorio | Constraints |
| --- | --- | --- | --- |
| id | integer | sim | chave primaria |
| entity_name | string | sim | entidade alterada |
| entity_id | integer | sim | id da entidade |
| action | string | sim | acao executada |
| details | json | sim | contexto da mudanca |
| created_at | datetime | sim | gerado pelo sistema |

## Relacionamentos

```text
Owner 1 ---- N Pet
Pet 1 ---- N Appointment N ---- 1 Veterinarian
Appointment 1 ---- 0..1 MedicalRecord
Pet 1 ---- N VaccinationRecord N ---- 1 Vaccine
Appointment 1 ---- N VaccinationRecord
Appointment 1 ---- N AuditEvent (por entity_name/entity_id)
```

Justificativa:

- Um tutor pode ter varios animais, mas cada animal tem um tutor principal.
- Uma consulta sempre pertence a um animal e a um veterinario; a agenda depende dos dois lados.
- Prontuario e opcional durante o fluxo, mas obrigatorio antes de concluir.
- Vacina e animal formam uma relacao N:N com atributos proprios: lote, data de aplicacao e reforco.
- Auditoria nao fica acoplada por FK porque pode registrar eventos de diferentes entidades.

## Maquina de estados

### Appointment

```text
scheduled -> checked_in -> in_progress -> completed
    |             |              |
    v             v              v
 canceled      canceled       canceled
```

Estados terminais:

- `completed`: atendimento encerrado, possui prontuario e valor final calculado.
- `canceled`: agenda encerrada sem atendimento.

Nao faz sentido sair de estados terminais porque isso alteraria historico clinico ou reabriria horario ja resolvido. Para corrigir erro operacional, a decisao correta seria registrar nova consulta ou evento de auditoria.

### Pet

```text
active -> in_treatment -> active
active -> inactive
active -> deceased
in_treatment -> deceased
```

`inactive` e `deceased` bloqueiam novos atendimentos e vacinacoes.

### Veterinarian

```text
active -> on_leave -> active
active -> inactive
on_leave -> inactive
```

Somente `active` permite receber novas consultas. `on_leave` representa afastamento temporario, enquanto `inactive` representa desligamento ou indisponibilidade permanente.

### Entidades sem ciclo de vida proprio

`Owner`, `MedicalRecord`, `Vaccine`, `VaccinationRecord` e `AuditEvent` nao possuem maquina de estados propria nesta modelagem. Elas sao registros cadastrais, clinicos ou historicos. Quando uma dessas entidades influencia regra de negocio, a regra usa atributos especificos, como `Vaccine.active`, ou o estado da entidade relacionada, como `Appointment.status`.

## Regras de negocio

### RN-001

| Item | Descricao |
| --- | --- |
| Identificador | RN-001 |
| Nome | Consulta nao pode sobrepor horario |
| Gatilho | Ao criar consulta |
| Pre-condicao | Consulta nova possui pet, veterinario, inicio e fim validos |
| Acao | Buscar consultas ativas (`scheduled`, `checked_in`, `in_progress`) que cruzem o mesmo periodo para o mesmo animal ou veterinario |
| Violacao | HTTP 409 com `APPOINTMENT_CONFLICT` e id/periodo da consulta conflitante |

### RN-002

| Item | Descricao |
| --- | --- |
| Identificador | RN-002 |
| Nome | Animal precisa estar apto para atendimento |
| Gatilho | Ao criar consulta ou vacinacao |
| Pre-condicao | Animal existe |
| Acao | Permitir somente status `active` ou `in_treatment` |
| Violacao | HTTP 409 com `PET_NOT_ELIGIBLE_FOR_CARE` e status atual |

### RN-003

| Item | Descricao |
| --- | --- |
| Identificador | RN-003 |
| Nome | Veterinario precisa estar disponivel |
| Gatilho | Ao criar consulta |
| Pre-condicao | Veterinario existe |
| Acao | Permitir somente veterinario com status `active` |
| Violacao | HTTP 409 com `VETERINARIAN_NOT_AVAILABLE` |

### RN-004

| Item | Descricao |
| --- | --- |
| Identificador | RN-004 |
| Nome | Transicao de estado deve respeitar o ciclo da consulta |
| Gatilho | Ao chamar `POST /appointments/{id}/status` |
| Pre-condicao | Consulta existe |
| Acao | Validar transicao na tabela `ALLOWED_TRANSITIONS` |
| Violacao | HTTP 409 com `INVALID_APPOINTMENT_TRANSITION`, estado atual, destino e destinos permitidos |

### RN-005

| Item | Descricao |
| --- | --- |
| Identificador | RN-005 |
| Nome | Consulta concluida exige prontuario |
| Gatilho | Ao tentar mover consulta para `completed` |
| Pre-condicao | Consulta esta em `in_progress` |
| Acao | Verificar existencia de `MedicalRecord` |
| Violacao | HTTP 409 com `MEDICAL_RECORD_REQUIRED` |

### RN-006

| Item | Descricao |
| --- | --- |
| Identificador | RN-006 |
| Nome | Vacinacao exige consulta concluida para o mesmo animal |
| Gatilho | Ao criar registro de vacinacao |
| Pre-condicao | Animal, vacina e consulta existem |
| Acao | Validar consulta `completed`, mesmo pet, vacina ativa e especie compativel |
| Violacao | HTTP 409 com `VACCINATION_REQUIRES_COMPLETED_APPOINTMENT`, `VACCINE_INACTIVE` ou `VACCINE_SPECIES_MISMATCH` |

## Calculo derivado

O valor final da consulta e calculado quando o prontuario e registrado:

```text
total_amount = veterinarian.base_consultation_fee + medical_record.procedure_cost + medical_record.medication_cost
```

Esse calculo fica na camada de servico porque depende de dados de entidades relacionadas.

## Validadores Pydantic

- `AppointmentCreate`: `ends_at` precisa ser posterior a `starts_at`.
- `PetCreate`: `birth_date` nao pode estar no futuro.
- `MedicalRecordCreate`: custos precisam ser maiores ou iguais a zero.
- `VaccinationCreate`: `booster_due_at` precisa ser posterior a `applied_at`.

Essas validacoes ficam nos schemas porque dependem apenas do payload recebido, sem consultar banco. Regras que dependem de outras entidades ficam nos services.

## Decisoes de design

1. Relacionamentos: `VaccinationRecord` foi modelada como entidade propria, nao como lista simples em Pet, porque a relacao Pet-Vaccine tem atributos do evento de aplicacao.
2. Regras no service: conflito de agenda, status de pet/veterinario e vacinacao dependem do banco e ficam fora dos routers.
3. Validators no Pydantic: datas e valores do proprio payload sao rejeitados antes de chegar ao service.
4. Migration 2: os indices compostos de agenda surgem da RN-001; sem eles, a busca por conflitos cresceria mal com muitos atendimentos.
5. Concorrencia: em producao, duas criacoes simultaneas de consulta para o mesmo horario devem ser protegidas por transacao com bloqueio ou constraint de exclusao no PostgreSQL. Esta entrega implementa a validacao deterministica no service e documenta o risco de race condition.
6. Estados terminais: `completed` e `canceled` nao retornam ao fluxo para preservar historico clinico e agenda.

## Cenarios de borda tratados

| Cenario | Decisao |
| --- | --- |
| Animal falecido ou inativo recebe nova consulta | Bloquear com `PET_NOT_ELIGIBLE_FOR_CARE` |
| Consulta sobrepoe horario de mesmo animal ou veterinario | Bloquear com `APPOINTMENT_CONFLICT` |
| Consulta cancelada tenta voltar para check-in | Bloquear com `INVALID_APPOINTMENT_TRANSITION` |
| Conclusao sem prontuario | Bloquear com `MEDICAL_RECORD_REQUIRED` |
| Vacina de especie diferente do animal | Bloquear com `VACCINE_SPECIES_MISMATCH` |
| Reforco de vacina antes da aplicacao | Bloquear no schema com `VALIDATION_ERROR` |

## Erros padronizados

Todos os erros seguem:

```json
{
  "error": "APPOINTMENT_CONFLICT",
  "message": "Ja existe uma consulta ativa para este animal ou veterinario no periodo solicitado.",
  "details": {
    "conflicting_appointment_id": 42,
    "period": {
      "start": "2030-01-01T10:00:00",
      "end": "2030-01-01T10:30:00"
    }
  }
}
```

## Migrations

1. `001_initial_clinic_structure`: cria tabelas principais do dominio.
2. `002_add_overlap_indexes`: adiciona indices compostos para validar conflito de agenda com desempenho adequado.
3. `003_add_audit_events`: adiciona tabela de auditoria para historico de transicoes de estado.

Todas possuem `downgrade`.

## Estrutura

```text
app/
  main.py
  core/
  models/
  schemas/
  services/
  repositories/
  routers/
alembic/
  versions/
tests/
Dockerfile
docker-compose.yml
.env.example
alembic.ini
requirements.txt
README.md
```
