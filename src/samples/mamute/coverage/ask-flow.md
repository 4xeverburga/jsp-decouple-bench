# Coverage — `ask-flow` (mamute)

## 1. Handler coverage (claim vs. execution)

**2/2 slice handlers driven and verified.**

### `org.mamute.controllers.QuestionController`

| handler               | slice   | claimed by                  | executed by                                                                                                                           | status            |
|-----------------------|---------|-----------------------------|---------------------------------------------------------------------------------------------------------------------------------------|-------------------|
| `showQuestion`        | yes     | ask-flow__question-creation | ask-flow__question-creation, ask-flow__question-without-watching, ask-flow__removed-question-not-found                                | verified          |
| `newQuestion`         | yes     | ask-flow__question-creation | ask-flow__illegal-tag-refused, ask-flow__question-creation, ask-flow__question-without-watching, ask-flow__removed-question-not-found | verified          |
| `questionForm`        |         | —                           | ask-flow__illegal-tag-refused, ask-flow__question-creation, ask-flow__question-without-watching, ask-flow__removed-question-not-found | outside the slice |
| `questionEditForm`    |         | —                           | —                                                                                                                                     | outside the slice |
| `edit`                |         | —                           | —                                                                                                                                     | outside the slice |
| `showVoteInformation` |         | —                           | —                                                                                                                                     | outside the slice |
| `deleteQuestion`      |         | —                           | —                                                                                                                                     | outside the slice |
| `deleteQuestionFully` |         | —                           | —                                                                                                                                     | outside the slice |

## 2. Line and branch coverage (JaCoCo, per case)

Slice = the lines of the slice's handlers; controller = the whole source file. Branches over several cases are a lower bound.

### `QuestionController`

| case                                 | slice lines   | slice branches   | controller lines   | controller branches   |
|--------------------------------------|---------------|------------------|--------------------|-----------------------|
| ask-flow__illegal-tag-refused        | 22% (10/45)   | 0% (0/6)         | 12% (13/104)       | 0% (0/18)             |
| ask-flow__question-creation          | 98% (44/45)   | 50% (3/6)        | 47% (49/104)       | 22% (4/18)            |
| ask-flow__question-without-watching  | 96% (43/45)   | 50% (3/6)        | 46% (48/104)       | 22% (4/18)            |
| ask-flow__removed-question-not-found | 100% (45/45)  | 67% (4/6)        | 48% (50/104)       | 28% (5/18)            |
| **all cases**                        | 100% (45/45)  | 67% (4/6)        | 48% (50/104)       | 28% (5/18)            |

App lines executed per case: ask-flow__illegal-tag-refused 26% (1475/5641), ask-flow__question-creation 30% (1678/5641), ask-flow__question-without-watching 30% (1670/5641), ask-flow__removed-question-not-found 33% (1864/5641)
