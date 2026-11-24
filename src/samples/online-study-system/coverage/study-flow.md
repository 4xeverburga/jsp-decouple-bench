# Coverage — `study-flow` (online-study-system)

## 1. Handler coverage (claim vs. execution)

**3/3 slice handlers driven and verified.**

### `com.wxs.controller.StudentController`

| handler             | slice   | claimed by                                  | executed by                                                                                                                                                               | status            |
|---------------------|---------|---------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|
| `startStudy`        | yes     | study-flow__next-period-increments-progress | study-flow__next-past-last-period-stays, study-flow__next-period-increments-progress, study-flow__prev-at-first-period-stays, study-flow__prev-period-decrements-progress | verified          |
| `changePeriod`      | yes     | study-flow__prev-period-decrements-progress | study-flow__prev-at-first-period-stays, study-flow__prev-period-decrements-progress                                                                                       | verified          |
| `backPeriod`        | yes     | study-flow__next-period-increments-progress | study-flow__next-past-last-period-stays, study-flow__next-period-increments-progress, study-flow__prev-period-decrements-progress                                         | verified          |
| `stuCourseShow`     |         | —                                           | study-flow__next-past-last-period-stays, study-flow__next-period-increments-progress, study-flow__prev-at-first-period-stays, study-flow__prev-period-decrements-progress | outside the slice |
| `findCourse`        |         | —                                           | —                                                                                                                                                                         | outside the slice |
| `stuSelectedCourse` |         | —                                           | —                                                                                                                                                                         | outside the slice |
| `selectedCourse`    |         | —                                           | study-flow__next-past-last-period-stays, study-flow__next-period-increments-progress, study-flow__prev-at-first-period-stays, study-flow__prev-period-decrements-progress | outside the slice |
| `startExam`         |         | —                                           | —                                                                                                                                                                         | outside the slice |
| `saveExam`          |         | —                                           | —                                                                                                                                                                         | outside the slice |
| `outCourse`         |         | —                                           | —                                                                                                                                                                         | outside the slice |
| `overCourse`        |         | —                                           | —                                                                                                                                                                         | outside the slice |
| `logout`            |         | —                                           | —                                                                                                                                                                         | outside the slice |
| `showSelf`          |         | —                                           | —                                                                                                                                                                         | outside the slice |
| `recharge`          |         | —                                           | —                                                                                                                                                                         | outside the slice |
| `updateBalance`     |         | —                                           | —                                                                                                                                                                         | outside the slice |
| `passwordRest`      |         | —                                           | —                                                                                                                                                                         | outside the slice |

## 2. Line and branch coverage (JaCoCo, per case)

Slice = the lines of the slice's handlers; controller = the whole source file. Branches over several cases are a lower bound.

### `StudentController`

| case                                        | slice lines   | slice branches   | controller lines   | controller branches   |
|---------------------------------------------|---------------|------------------|--------------------|-----------------------|
| study-flow__next-past-last-period-stays     | 63% (17/27)   | 50% (2/4)        | 41% (59/145)       | 29% (7/24)            |
| study-flow__next-period-increments-progress | 63% (17/27)   | 25% (1/4)        | 41% (59/145)       | 25% (6/24)            |
| study-flow__prev-at-first-period-stays      | 44% (12/27)   | 25% (1/4)        | 37% (54/145)       | 25% (6/24)            |
| study-flow__prev-period-decrements-progress | 100% (27/27)  | 50% (2/4)        | 48% (69/145)       | 29% (7/24)            |
| **all cases**                               | 100% (27/27)  | 75% (3/4)        | 48% (69/145)       | 33% (8/24)            |

App lines executed per case: study-flow__next-past-last-period-stays 18% (367/2032), study-flow__next-period-increments-progress 18% (367/2032), study-flow__prev-at-first-period-stays 18% (356/2032), study-flow__prev-period-decrements-progress 19% (377/2032)
