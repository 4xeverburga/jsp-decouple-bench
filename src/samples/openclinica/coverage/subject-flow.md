# Coverage — `subject-flow` (openclinica)

## 1. Handler coverage (claim vs. execution)

**2/2 slice handlers driven and verified.**

### `org.akaza.openclinica.control.submit.AddNewSubjectServlet`

| handler            | slice   | claimed by                     | executed by                                                                                                                                                                                                                                                      | status            |
|--------------------|---------|--------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|
| `processRequest`   | yes     | subject-flow__subject-creation | subject-flow__blank-fields-refused, subject-flow__duplicate-label-refused, subject-flow__duplicate-person-id-refused, subject-flow__invalid-fields-refused, subject-flow__save-and-add-next, subject-flow__save-and-assign-event, subject-flow__subject-creation | verified          |
| `createStudyEvent` |         | —                              | —                                                                                                                                                                                                                                                                | outside the slice |
| `mayProceed`       |         | —                              | subject-flow__blank-fields-refused, subject-flow__duplicate-label-refused, subject-flow__duplicate-person-id-refused, subject-flow__invalid-fields-refused, subject-flow__save-and-add-next, subject-flow__save-and-assign-event, subject-flow__subject-creation | outside the slice |

### `org.akaza.openclinica.control.submit.ListStudySubjectsServlet`

| handler          | slice   | claimed by                     | executed by                                                                                                                                                                                                                                                      | status            |
|------------------|---------|--------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|
| `processRequest` | yes     | subject-flow__subject-creation | subject-flow__blank-fields-refused, subject-flow__duplicate-label-refused, subject-flow__duplicate-person-id-refused, subject-flow__invalid-fields-refused, subject-flow__save-and-add-next, subject-flow__save-and-assign-event, subject-flow__subject-creation | verified          |
| `mayProceed`     |         | —                              | subject-flow__blank-fields-refused, subject-flow__duplicate-label-refused, subject-flow__duplicate-person-id-refused, subject-flow__invalid-fields-refused, subject-flow__save-and-add-next, subject-flow__save-and-assign-event, subject-flow__subject-creation | outside the slice |

## 2. Line and branch coverage (JaCoCo, per case)

Slice = the lines of the slice's handlers; controller = the whole source file. Branches over several cases are a lower bound.

### `AddNewSubjectServlet`

| case                                      | slice lines   | slice branches   | controller lines   | controller branches   |
|-------------------------------------------|---------------|------------------|--------------------|-----------------------|
| subject-flow__blank-fields-refused        | 28% (110/395) | 18% (33/184)     | 26% (125/490)      | 16% (35/224)          |
| subject-flow__duplicate-label-refused     | 44% (172/395) | 30% (56/184)     | 40% (194/490)      | 29% (65/224)          |
| subject-flow__duplicate-person-id-refused | 44% (175/395) | 31% (57/184)     | 40% (197/490)      | 29% (66/224)          |
| subject-flow__invalid-fields-refused      | 33% (129/395) | 20% (36/184)     | 29% (144/490)      | 17% (38/224)          |
| subject-flow__save-and-add-next           | 40% (159/395) | 29% (54/184)     | 37% (181/490)      | 28% (63/224)          |
| subject-flow__save-and-assign-event       | 37% (145/395) | 27% (50/184)     | 34% (167/490)      | 26% (59/224)          |
| subject-flow__subject-creation            | 37% (148/395) | 28% (51/184)     | 35% (170/490)      | 27% (60/224)          |
| **all cases**                             | 50% (198/395) | 33% (61/184)     | 45% (220/490)      | 31% (70/224)          |

### `ListStudySubjectsServlet`

| case                                      | slice lines   | slice branches   | controller lines   | controller branches   |
|-------------------------------------------|---------------|------------------|--------------------|-----------------------|
| subject-flow__blank-fields-refused        | 63% (17/27)   | 38% (6/16)       | 81% (67/83)        | 43% (18/42)           |
| subject-flow__duplicate-label-refused     | 63% (17/27)   | 38% (6/16)       | 81% (67/83)        | 43% (18/42)           |
| subject-flow__duplicate-person-id-refused | 63% (17/27)   | 38% (6/16)       | 81% (67/83)        | 43% (18/42)           |
| subject-flow__invalid-fields-refused      | 63% (17/27)   | 38% (6/16)       | 81% (67/83)        | 43% (18/42)           |
| subject-flow__save-and-add-next           | 63% (17/27)   | 38% (6/16)       | 81% (67/83)        | 43% (18/42)           |
| subject-flow__save-and-assign-event       | 67% (18/27)   | 44% (7/16)       | 82% (68/83)        | 71% (30/42)           |
| subject-flow__subject-creation            | 63% (17/27)   | 38% (6/16)       | 81% (67/83)        | 43% (18/42)           |
| **all cases**                             | 67% (18/27)   | 44% (7/16)       | 82% (68/83)        | 71% (30/42)           |

App lines executed per case: subject-flow__blank-fields-refused 4% (2139/54444), subject-flow__duplicate-label-refused 5% (2500/54444), subject-flow__duplicate-person-id-refused 5% (2503/54444), subject-flow__invalid-fields-refused 4% (2164/54444), subject-flow__save-and-add-next 4% (2251/54444), subject-flow__save-and-assign-event 4% (2312/54444), subject-flow__subject-creation 5% (2466/54444)
