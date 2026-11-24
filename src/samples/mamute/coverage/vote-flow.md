# Coverage — `vote-flow` (mamute)

## 1. Handler coverage (claim vs. execution)

**4/4 slice handlers driven and verified.**

### `org.mamute.controllers.VoteController`

| handler           | slice   | claimed by                                 | executed by                                                                                                                | status   |
|-------------------|---------|--------------------------------------------|----------------------------------------------------------------------------------------------------------------------------|----------|
| `voteUp`          | yes     | vote-flow__upvote-increments-count         | vote-flow__upvote-increments-count, vote-flow__upvote-removal-restores-count, vote-flow__upvote-then-downvote-switches     | verified |
| `voteDown`        | yes     | vote-flow__downvote-decrements-count       | vote-flow__downvote-decrements-count, vote-flow__downvote-removal-restores-count, vote-flow__upvote-then-downvote-switches | verified |
| `voteUpRemoval`   | yes     | vote-flow__upvote-removal-restores-count   | vote-flow__upvote-removal-restores-count                                                                                   | verified |
| `voteDownRemoval` | yes     | vote-flow__downvote-removal-restores-count | vote-flow__downvote-removal-restores-count                                                                                 | verified |

## 2. Line and branch coverage (JaCoCo, per case)

Slice = the lines of the slice's handlers; controller = the whole source file. Branches over several cases are a lower bound.

### `VoteController`

| case                                       | slice lines   | slice branches   | controller lines   | controller branches   |
|--------------------------------------------|---------------|------------------|--------------------|-----------------------|
| vote-flow__downvote-decrements-count       | 20% (2/10)    | n/a              | 33% (10/30)        | n/a                   |
| vote-flow__downvote-removal-restores-count | 40% (4/10)    | n/a              | 60% (18/30)        | n/a                   |
| vote-flow__upvote-increments-count         | 30% (3/10)    | n/a              | 37% (11/30)        | n/a                   |
| vote-flow__upvote-removal-restores-count   | 60% (6/10)    | n/a              | 67% (20/30)        | n/a                   |
| vote-flow__upvote-then-downvote-switches   | 50% (5/10)    | n/a              | 43% (13/30)        | n/a                   |
| **all cases**                              | 100% (10/10)  | n/a              | 80% (24/30)        | n/a                   |

App lines executed per case: vote-flow__downvote-decrements-count 34% (1904/5641), vote-flow__downvote-removal-restores-count 34% (1945/5641), vote-flow__upvote-increments-count 34% (1907/5641), vote-flow__upvote-removal-restores-count 35% (1949/5641), vote-flow__upvote-then-downvote-switches 34% (1930/5641)
