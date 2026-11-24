# Coverage — `select-course-flow` (online-study-system)

## 1. Handler coverage (claim vs. execution)

**2/2 slice handlers driven and verified.**

### `com.wxs.controller.StudentController`

| handler             | slice   | claimed by                                        | executed by                                                                                                                                                | status            |
|---------------------|---------|---------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|
| `stuSelectedCourse` | yes     | select-course-flow__select-course-deducts-balance | select-course-flow__already-selected-refused, select-course-flow__insufficient-balance-blocks-selection, select-course-flow__select-course-deducts-balance | verified          |
| `selectedCourse`    | yes     | select-course-flow__select-course-deducts-balance | select-course-flow__select-course-deducts-balance                                                                                                          | verified          |
| `stuCourseShow`     |         | —                                                 | select-course-flow__already-selected-refused, select-course-flow__insufficient-balance-blocks-selection, select-course-flow__select-course-deducts-balance | outside the slice |
| `findCourse`        |         | —                                                 | —                                                                                                                                                          | outside the slice |
| `startStudy`        |         | —                                                 | —                                                                                                                                                          | outside the slice |
| `changePeriod`      |         | —                                                 | —                                                                                                                                                          | outside the slice |
| `backPeriod`        |         | —                                                 | —                                                                                                                                                          | outside the slice |
| `startExam`         |         | —                                                 | —                                                                                                                                                          | outside the slice |
| `saveExam`          |         | —                                                 | —                                                                                                                                                          | outside the slice |
| `outCourse`         |         | —                                                 | —                                                                                                                                                          | outside the slice |
| `overCourse`        |         | —                                                 | —                                                                                                                                                          | outside the slice |
| `logout`            |         | —                                                 | —                                                                                                                                                          | outside the slice |
| `showSelf`          |         | —                                                 | —                                                                                                                                                          | outside the slice |
| `recharge`          |         | —                                                 | —                                                                                                                                                          | outside the slice |
| `updateBalance`     |         | —                                                 | —                                                                                                                                                          | outside the slice |
| `passwordRest`      |         | —                                                 | —                                                                                                                                                          | outside the slice |

## 2. Line and branch coverage (JaCoCo, per case)

Slice = the lines of the slice's handlers; controller = the whole source file. Branches over several cases are a lower bound.

### `StudentController`

| case                                                      | slice lines   | slice branches   | controller lines   | controller branches   |
|-----------------------------------------------------------|---------------|------------------|--------------------|-----------------------|
| select-course-flow__already-selected-refused              | 15% (4/27)    | 17% (1/6)        | 20% (29/145)       | 17% (4/24)            |
| select-course-flow__insufficient-balance-blocks-selection | 33% (9/27)    | 33% (2/6)        | 23% (34/145)       | 21% (5/24)            |
| select-course-flow__select-course-deducts-balance         | 85% (23/27)   | 50% (3/6)        | 41% (60/145)       | 33% (8/24)            |
| **all cases**                                             | 93% (25/27)   | 50% (3/6)        | 43% (62/145)       | 33% (8/24)            |

App lines executed per case: select-course-flow__already-selected-refused 16% (318/2032), select-course-flow__insufficient-balance-blocks-selection 16% (332/2032), select-course-flow__select-course-deducts-balance 19% (391/2032)
