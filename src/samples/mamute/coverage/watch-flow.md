# Coverage — `watch-flow` (mamute)

## 1. Handler coverage (claim vs. execution)

**1/1 slice handlers driven and verified.**

### `org.mamute.controllers.WatchController`

| handler   | slice   | claimed by                     | executed by                                                         | status   |
|-----------|---------|--------------------------------|---------------------------------------------------------------------|----------|
| `watch`   | yes     | watch-flow__watch-adds-watcher | watch-flow__unwatch-removes-watcher, watch-flow__watch-adds-watcher | verified |

## 2. Line and branch coverage (JaCoCo, per case)

Slice = the lines of the slice's handlers; controller = the whole source file. Branches over several cases are a lower bound.

### `WatchController`

| case                                | slice lines   | slice branches   | controller lines   | controller branches   |
|-------------------------------------|---------------|------------------|--------------------|-----------------------|
| watch-flow__unwatch-removes-watcher | 100% (6/6)    | n/a              | 100% (7/7)         | n/a                   |
| watch-flow__watch-adds-watcher      | 100% (6/6)    | n/a              | 100% (7/7)         | n/a                   |
| **all cases**                       | 100% (6/6)    | n/a              | 100% (7/7)         | n/a                   |

App lines executed per case: watch-flow__unwatch-removes-watcher 30% (1715/5641), watch-flow__watch-adds-watcher 30% (1702/5641)
