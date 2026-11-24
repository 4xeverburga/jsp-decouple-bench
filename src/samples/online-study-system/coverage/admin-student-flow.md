# Coverage — `admin-student-flow` (online-study-system)

## 1. Handler coverage (claim vs. execution)

**4/4 slice handlers driven and verified.**

### `com.wxs.controller.AdminController`

| handler              | slice   | claimed by                                   | executed by                                                                                                                               | status            |
|----------------------|---------|----------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|-------------------|
| `showStudent`        | yes     | admin-student-flow__add-student-creates-user | admin-student-flow__add-student-creates-user, admin-student-flow__pager-links-on-single-page, admin-student-flow__remove-student-cascades | verified          |
| `addStudentUI`       | yes     | admin-student-flow__add-student-creates-user | admin-student-flow__add-student-creates-user                                                                                              | verified          |
| `addStudent`         | yes     | admin-student-flow__add-student-creates-user | admin-student-flow__add-student-creates-user                                                                                              | verified          |
| `removeStudent`      | yes     | admin-student-flow__remove-student-cascades  | admin-student-flow__remove-student-cascades                                                                                               | verified          |
| `showCourse`         |         | —                                            | admin-student-flow__add-student-creates-user, admin-student-flow__pager-links-on-single-page, admin-student-flow__remove-student-cascades | outside the slice |
| `editCourseUI`       |         | —                                            | —                                                                                                                                         | outside the slice |
| `editCourse`         |         | —                                            | —                                                                                                                                         | outside the slice |
| `removeCourse`       |         | —                                            | —                                                                                                                                         | outside the slice |
| `selectCourse`       |         | —                                            | —                                                                                                                                         | outside the slice |
| `addCourseUI`        |         | —                                            | —                                                                                                                                         | outside the slice |
| `addCourse`          |         | —                                            | —                                                                                                                                         | outside the slice |
| `editStudentUI`      |         | —                                            | —                                                                                                                                         | outside the slice |
| `editStudent`        |         | —                                            | —                                                                                                                                         | outside the slice |
| `selectStudent`      |         | —                                            | —                                                                                                                                         | outside the slice |
| `showTeacher`        |         | —                                            | —                                                                                                                                         | outside the slice |
| `addTeacherUI`       |         | —                                            | —                                                                                                                                         | outside the slice |
| `addTeacher`         |         | —                                            | —                                                                                                                                         | outside the slice |
| `editTeacherUI`      |         | —                                            | —                                                                                                                                         | outside the slice |
| `editTeacher`        |         | —                                            | —                                                                                                                                         | outside the slice |
| `removeTeacher`      |         | —                                            | —                                                                                                                                         | outside the slice |
| `selectTeacher`      |         | —                                            | —                                                                                                                                         | outside the slice |
| `logout`             |         | —                                            | —                                                                                                                                         | outside the slice |
| `userPasswordRestUI` |         | —                                            | —                                                                                                                                         | outside the slice |
| `userPasswordRest`   |         | —                                            | —                                                                                                                                         | outside the slice |
| `passwordRestUI`     |         | —                                            | —                                                                                                                                         | outside the slice |

## 2. Line and branch coverage (JaCoCo, per case)

Slice = the lines of the slice's handlers; controller = the whole source file. Branches over several cases are a lower bound.

### `AdminController`

| case                                           | slice lines   | slice branches   | controller lines   | controller branches   |
|------------------------------------------------|---------------|------------------|--------------------|-----------------------|
| admin-student-flow__add-student-creates-user   | 62% (21/34)   | 20% (2/10)       | 27% (45/166)       | 13% (6/46)            |
| admin-student-flow__pager-links-on-single-page | 32% (11/34)   | 40% (4/10)       | 21% (35/166)       | 17% (8/46)            |
| admin-student-flow__remove-student-cascades    | 56% (19/34)   | 50% (5/10)       | 26% (43/166)       | 20% (9/46)            |
| **all cases**                                  | 97% (33/34)   | 90% (9/10)       | 34% (57/166)       | 28% (13/46)           |

App lines executed per case: admin-student-flow__add-student-creates-user 17% (336/2032), admin-student-flow__pager-links-on-single-page 15% (311/2032), admin-student-flow__remove-student-cascades 20% (397/2032)
