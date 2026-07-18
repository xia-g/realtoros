# Failure Injection — Results

## Data Failures

| Failure | Expected | Actual | Result |
|---------|----------|--------|--------|
| Duplicate batch | PK violation | PK constraint | ✅ |
| Event without document | processes normally | processes normally | ✅ |
| Non-existent snapshot | ValueError | ValueError | ✅ |
| Decision without posting | gap in reconciliation | gap detected | ✅ |

## Lifecycle Failures

| Failure | Expected | Actual | Result |
|---------|----------|--------|--------|
| Post to closed period | blocked by PostingEngine | blocked | ✅ |
| Report replay | identical hash | identical hash | ✅ |
| New policy version | old report unchanged | unchanged | ✅ |

## Operations Failures

| Failure | Expected | Actual | Result |
|---------|----------|--------|--------|
| Readonly executes close_period | denied | 'not allowed' | ✅ |
| Accountant executes full_replay | denied | denied | ✅ |
| close_period without approval | pending_approval | pending_approval | ✅ |

## Recovery Paths

| Scenario | Recovery | Immutability |
|----------|----------|-------------|
| Failed action | retry via API | audit trail preserved |
| Rejected approval | re-approve with admin | approval log preserved |
| Closed period replay | delta posting to open period | old posting immutable |
