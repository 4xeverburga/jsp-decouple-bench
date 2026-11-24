# Coverage — `answer-flow` (mamute)

## 1. Handler coverage (claim vs. execution)

**2/2 slice handlers driven and verified.**

### `org.mamute.controllers.AnswerController`

| handler          | slice   | claimed by                  | executed by                                                                                                                                         | status            |
|------------------|---------|-----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|
| `newAnswer`      | yes     | answer-flow__answer-appears | answer-flow__answer-appears, answer-flow__answer-without-watching, answer-flow__moderator-answers-own-question, answer-flow__second-answer-rejected | verified          |
| `answerEditForm` |         | —                           | —                                                                                                                                                   | outside the slice |
| `edit`           |         | —                           | —                                                                                                                                                   | outside the slice |
| `markAsSolution` |         | —                           | —                                                                                                                                                   | outside the slice |
| `delete`         |         | —                           | —                                                                                                                                                   | outside the slice |

### `org.mamute.controllers.QuestionController`

| handler               | slice   | claimed by                  | executed by                                                                                                                                                                                  | status            |
|-----------------------|---------|-----------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|
| `showQuestion`        | yes     | answer-flow__answer-appears | answer-flow__answer-appears, answer-flow__answer-without-watching, answer-flow__moderator-answers-own-question, answer-flow__own-question-form-withheld, answer-flow__second-answer-rejected | verified          |
| `questionForm`        |         | —                           | answer-flow__answer-appears, answer-flow__answer-without-watching, answer-flow__moderator-answers-own-question, answer-flow__own-question-form-withheld, answer-flow__second-answer-rejected | outside the slice |
| `questionEditForm`    |         | —                           | —                                                                                                                                                                                            | outside the slice |
| `edit`                |         | —                           | —                                                                                                                                                                                            | outside the slice |
| `newQuestion`         |         | —                           | answer-flow__answer-appears, answer-flow__answer-without-watching, answer-flow__moderator-answers-own-question, answer-flow__own-question-form-withheld, answer-flow__second-answer-rejected | outside the slice |
| `showVoteInformation` |         | —                           | —                                                                                                                                                                                            | outside the slice |
| `deleteQuestion`      |         | —                           | —                                                                                                                                                                                            | outside the slice |
| `deleteQuestionFully` |         | —                           | —                                                                                                                                                                                            | outside the slice |

## 2. Line and branch coverage (JaCoCo, per case)

Slice = the lines of the slice's handlers; controller = the whole source file. Branches over several cases are a lower bound.

### `AnswerController`

| case                                        | slice lines   | slice branches   | controller lines   | controller branches   |
|---------------------------------------------|---------------|------------------|--------------------|-----------------------|
| answer-flow__answer-appears                 | 91% (20/22)   | 50% (3/6)        | 22% (21/95)        | 12% (3/24)            |
| answer-flow__answer-without-watching        | 86% (19/22)   | 50% (3/6)        | 21% (20/95)        | 12% (3/24)            |
| answer-flow__moderator-answers-own-question | 91% (20/22)   | 50% (3/6)        | 22% (21/95)        | 12% (3/24)            |
| answer-flow__own-question-form-withheld     | 0% (0/22)     | 0% (0/6)         | 0% (0/95)          | 0% (0/24)             |
| answer-flow__second-answer-rejected         | 95% (21/22)   | 67% (4/6)        | 23% (22/95)        | 17% (4/24)            |
| **all cases**                               | 95% (21/22)   | 67% (4/6)        | 23% (22/95)        | 17% (4/24)            |

### `QuestionController`

| case                                        | slice lines   | slice branches   | controller lines   | controller branches   |
|---------------------------------------------|---------------|------------------|--------------------|-----------------------|
| answer-flow__answer-appears                 | 95% (21/22)   | 50% (2/4)        | 47% (49/104)       | 22% (4/18)            |
| answer-flow__answer-without-watching        | 95% (21/22)   | 50% (2/4)        | 47% (49/104)       | 22% (4/18)            |
| answer-flow__moderator-answers-own-question | 95% (21/22)   | 50% (2/4)        | 47% (49/104)       | 22% (4/18)            |
| answer-flow__own-question-form-withheld     | 95% (21/22)   | 50% (2/4)        | 47% (49/104)       | 22% (4/18)            |
| answer-flow__second-answer-rejected         | 95% (21/22)   | 50% (2/4)        | 47% (49/104)       | 22% (4/18)            |
| **all cases**                               | 95% (21/22)   | 50% (2/4)        | 47% (49/104)       | 22% (4/18)            |

App lines executed per case: answer-flow__answer-appears 35% (1958/5641), answer-flow__answer-without-watching 35% (1957/5641), answer-flow__moderator-answers-own-question 32% (1801/5641), answer-flow__own-question-form-withheld 30% (1679/5641), answer-flow__second-answer-rejected 35% (1963/5641)
