# Coverage — `teacher-mark-flow` (online-study-system)

## 1. Handler coverage (claim vs. execution)

**3/3 slice handlers driven and verified.**

### `com.wxs.controller.TeacherController`

| handler         | slice   | claimed by                              | executed by                                                                           | status            |
|-----------------|---------|-----------------------------------------|---------------------------------------------------------------------------------------|-------------------|
| `gradeCourse`   | yes     | teacher-mark-flow__save-mark-sets-grade | teacher-mark-flow__mark-without-exam-refused, teacher-mark-flow__save-mark-sets-grade | verified          |
| `markUI`        | yes     | teacher-mark-flow__save-mark-sets-grade | teacher-mark-flow__mark-without-exam-refused, teacher-mark-flow__save-mark-sets-grade | verified          |
| `mark`          | yes     | teacher-mark-flow__save-mark-sets-grade | teacher-mark-flow__save-mark-sets-grade                                               | verified          |
| `logout`        |         | —                                       | —                                                                                     | outside the slice |
| `showSelf`      |         | —                                       | —                                                                                     | outside the slice |
| `stuCourseShow` |         | —                                       | teacher-mark-flow__mark-without-exam-refused, teacher-mark-flow__save-mark-sets-grade | outside the slice |
| `findCourse`    |         | —                                       | —                                                                                     | outside the slice |
| `passwordRest`  |         | —                                       | —                                                                                     | outside the slice |

## 2. Line and branch coverage (JaCoCo, per case)

Slice = the lines of the slice's handlers; controller = the whole source file. Branches over several cases are a lower bound.

### `TeacherController`

| case                                         | slice lines   | slice branches   | controller lines   | controller branches   |
|----------------------------------------------|---------------|------------------|--------------------|-----------------------|
| teacher-mark-flow__mark-without-exam-refused | 50% (8/16)    | 50% (2/4)        | 54% (31/57)        | 50% (4/8)             |
| teacher-mark-flow__save-mark-sets-grade      | 88% (14/16)   | 50% (2/4)        | 65% (37/57)        | 50% (4/8)             |
| **all cases**                                | 94% (15/16)   | 50% (2/4)        | 67% (38/57)        | 50% (4/8)             |

App lines executed per case: teacher-mark-flow__mark-without-exam-refused 22% (456/2032), teacher-mark-flow__save-mark-sets-grade 23% (474/2032)
