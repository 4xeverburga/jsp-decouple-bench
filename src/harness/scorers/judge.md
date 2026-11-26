You are reviewing whether a change to a server-rendered Java web app did
what its work order asked. You do not see the code. You see two span trees,
recorded by OpenTelemetry while the same scripted browser flow ran twice:
BEFORE, on the app as it was, and AFTER, on the changed app. The browser's
behaviour has already been checked separately; your question is only how
the app served it.

How to read a tree:

- Each top-level `SERVER <method> <path> -> <status>` line is one request
  the browser made, in order. `renders <view>` means the request ended by
  rendering that server-side view.
- The lines under a request are what happened while serving it, in order.
  `SQL <operation> <table>` is a statement the app sent to its database.
  `HTTP CLIENT <method> <path> -> <status>` is an HTTP request the app
  itself made. A `SERVER` line nested under an `HTTP CLIENT` line is the
  app answering that request: a real call over the wire to its own
  backend, and the lines under it are the backend's work. Any other line is
  a framework event, such as a redirect.
- Numbers and slugs in paths are erased as `{n}` and `{slug}`. `xN` folds N
  identical consecutive siblings.
- Some SQL runs on every request whatever it does: session lookup, an
  access check, data for the page layout. You can recognise it because in
  BEFORE it also appears under requests unrelated to the work order, such
  as the login page or a static message endpoint. That per-request work is
  not part of the work order; it may stay under the page's request, and it
  may repeat under the backend's.

The work order the change was made from:

<work_order>
{work_order}
</work_order>

The requests in scope were decided by whoever wrote this case, not by
you. Each line below is a `SERVER` line as it appears in BEFORE, and it
covers every occurrence of that line in the flow:

<scope>
{scope}
</scope>

`move: all` means every statement of the in-scope work under that request
must now run under the backend's nested span. `move: writes` means only
its writes (INSERT, UPDATE, DELETE) must; its reads may stay on the page
side. A request not listed is out of scope: it may be left as it was, and
decoupling it too is not a fault. Do not add a request to the scope, and
do not drop one from it.

Decide each of these from the trees alone:

1. `browser_contract_kept` — AFTER has the same browser requests as
   BEFORE: same methods, paths and statuses, same views rendered, same
   order. Ignore differences in the per-request SQL.
2. `boundary_crossed` — every in-scope request now makes an
   `HTTP CLIENT` call while it is served, answered by a nested `SERVER`
   span, and the work its `move` asks for runs under that span: all of
   its in-scope SQL for `move: all`, its writes for `move: writes`.
3. `page_side_clean` — under each `move: all` request, AFTER keeps no SQL
   of the in-scope work outside the backend's nested span: only the
   per-request work described above. A `move: writes` request passes this
   criterion as long as it keeps no write outside that span.
4. `writes_preserved` — every write BEFORE made for the in-scope work
   (INSERT, UPDATE or DELETE, by table) still happens in AFTER, now under
   the backend's span. Reads may differ in number.

In `explanation`, cite the lines
that decided each criterion that failed, or say in a sentence why all of
them hold. Answer with the JSON object only.

BEFORE (the app as it was):

<before>
{before}
</before>

AFTER (the changed app):

<after>
{after}
</after>
