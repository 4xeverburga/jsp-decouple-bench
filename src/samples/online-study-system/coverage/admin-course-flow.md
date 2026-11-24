# Coverage — `admin-course-flow` (online-study-system)

## 1. Handler coverage (claim vs. execution)

**3/3 slice handlers driven and verified.**

### `com.wxs.controller.AdminController`

| handler              | slice   | claimed by                                   | executed by                                                                                 | status            |
|----------------------|---------|----------------------------------------------|---------------------------------------------------------------------------------------------|-------------------|
| `showCourse`         | yes     | admin-course-flow__add-course-creates-course | admin-course-flow__add-course-creates-course, admin-course-flow__pager-links-on-single-page | verified          |
| `addCourseUI`        | yes     | admin-course-flow__add-course-creates-course | admin-course-flow__add-course-creates-course                                                | verified          |
| `addCourse`          | yes     | admin-course-flow__add-course-creates-course | admin-course-flow__add-course-creates-course                                                | verified          |
| `editCourseUI`       |         | —                                            | —                                                                                           | outside the slice |
| `editCourse`         |         | —                                            | —                                                                                           | outside the slice |
| `removeCourse`       |         | —                                            | —                                                                                           | outside the slice |
| `selectCourse`       |         | —                                            | —                                                                                           | outside the slice |
| `showStudent`        |         | —                                            | —                                                                                           | outside the slice |
| `addStudentUI`       |         | —                                            | —                                                                                           | outside the slice |
| `addStudent`         |         | —                                            | —                                                                                           | outside the slice |
| `editStudentUI`      |         | —                                            | —                                                                                           | outside the slice |
| `editStudent`        |         | —                                            | —                                                                                           | outside the slice |
| `removeStudent`      |         | —                                            | —                                                                                           | outside the slice |
| `selectStudent`      |         | —                                            | —                                                                                           | outside the slice |
| `showTeacher`        |         | —                                            | —                                                                                           | outside the slice |
| `addTeacherUI`       |         | —                                            | —                                                                                           | outside the slice |
| `addTeacher`         |         | —                                            | —                                                                                           | outside the slice |
| `editTeacherUI`      |         | —                                            | —                                                                                           | outside the slice |
| `editTeacher`        |         | —                                            | —                                                                                           | outside the slice |
| `removeTeacher`      |         | —                                            | —                                                                                           | outside the slice |
| `selectTeacher`      |         | —                                            | —                                                                                           | outside the slice |
| `logout`             |         | —                                            | —                                                                                           | outside the slice |
| `userPasswordRestUI` |         | —                                            | —                                                                                           | outside the slice |
| `userPasswordRest`   |         | —                                            | —                                                                                           | outside the slice |
| `passwordRestUI`     |         | —                                            | —                                                                                           | outside the slice |

## 2. Line and branch coverage (JaCoCo, per case)

Slice = the lines of the slice's handlers; controller = the whole source file. Branches over several cases are a lower bound.

### `AdminController`

| case                                          | slice lines   | slice branches   | controller lines   | controller branches   |
|-----------------------------------------------|---------------|------------------|--------------------|-----------------------|
| admin-course-flow__add-course-creates-course  | 88% (15/17)   | 25% (1/4)        | 17% (29/166)       | 9% (4/46)             |
| admin-course-flow__pager-links-on-single-page | 71% (12/17)   | 100% (4/4)       | 16% (26/166)       | 15% (7/46)            |
| **all cases**                                 | 100% (17/17)  | 100% (4/4)       | 19% (31/166)       | 15% (7/46)            |

App lines executed per case: admin-course-flow__add-course-creates-course 14% (288/2032), admin-course-flow__pager-links-on-single-page 12% (246/2032)
