# Coverage — `exam-flow` (online-study-system)

## 1. Handler coverage (claim vs. execution)

**2/2 slice handlers driven and verified.**

### `com.wxs.controller.StudentController`

| handler             | slice   | claimed by                          | executed by                                                                                                      | status            |
|---------------------|---------|-------------------------------------|------------------------------------------------------------------------------------------------------------------|-------------------|
| `startExam`         | yes     | exam-flow__save-exam-marks-has-exam | exam-flow__exam-before-periods-done-refused, exam-flow__save-exam-marks-has-exam, exam-flow__second-exam-refused | verified          |
| `saveExam`          | yes     | exam-flow__save-exam-marks-has-exam | exam-flow__save-exam-marks-has-exam, exam-flow__second-exam-refused                                              | verified          |
| `stuCourseShow`     |         | —                                   | exam-flow__exam-before-periods-done-refused, exam-flow__save-exam-marks-has-exam, exam-flow__second-exam-refused | outside the slice |
| `findCourse`        |         | —                                   | —                                                                                                                | outside the slice |
| `stuSelectedCourse` |         | —                                   | —                                                                                                                | outside the slice |
| `selectedCourse`    |         | —                                   | exam-flow__exam-before-periods-done-refused, exam-flow__save-exam-marks-has-exam, exam-flow__second-exam-refused | outside the slice |
| `startStudy`        |         | —                                   | exam-flow__save-exam-marks-has-exam, exam-flow__second-exam-refused                                              | outside the slice |
| `changePeriod`      |         | —                                   | —                                                                                                                | outside the slice |
| `backPeriod`        |         | —                                   | exam-flow__save-exam-marks-has-exam, exam-flow__second-exam-refused                                              | outside the slice |
| `outCourse`         |         | —                                   | —                                                                                                                | outside the slice |
| `overCourse`        |         | —                                   | —                                                                                                                | outside the slice |
| `logout`            |         | —                                   | —                                                                                                                | outside the slice |
| `showSelf`          |         | —                                   | —                                                                                                                | outside the slice |
| `recharge`          |         | —                                   | —                                                                                                                | outside the slice |
| `updateBalance`     |         | —                                   | —                                                                                                                | outside the slice |
| `passwordRest`      |         | —                                   | —                                                                                                                | outside the slice |

## 2. Line and branch coverage (JaCoCo, per case)

Slice = the lines of the slice's handlers; controller = the whole source file. Branches over several cases are a lower bound.

### `StudentController`

| case                                        | slice lines   | slice branches   | controller lines   | controller branches   |
|---------------------------------------------|---------------|------------------|--------------------|-----------------------|
| exam-flow__exam-before-periods-done-refused | 35% (7/20)    | 25% (1/4)        | 34% (49/145)       | 25% (6/24)            |
| exam-flow__save-exam-marks-has-exam         | 90% (18/20)   | 50% (2/4)        | 53% (77/145)       | 33% (8/24)            |
| exam-flow__second-exam-refused              | 95% (19/20)   | 75% (3/4)        | 54% (78/145)       | 38% (9/24)            |
| **all cases**                               | 100% (20/20)  | 75% (3/4)        | 54% (79/145)       | 38% (9/24)            |

App lines executed per case: exam-flow__exam-before-periods-done-refused 18% (362/2032), exam-flow__save-exam-marks-has-exam 19% (390/2032), exam-flow__second-exam-refused 20% (402/2032)
