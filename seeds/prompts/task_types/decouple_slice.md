This app renders its pages on the server, and the controllers that
render them also do the work: they call services and data-access code
in-process and hand the results to the views.

The job is to put a boundary between the two, inside the same app, for
the part described below. The work moves behind backend controllers
that answer with JSON and enforce the rules for any caller. The
page-side controllers stop calling services and data-access code; they
call the backend over HTTP on the app's own address — taken from
configuration or the request, not hard-coded — forwarding the signed-in
user, and render the same views from what comes back.

The call has to be a real request over the wire. Calling the backend
controller's method, passing objects in memory or forwarding inside the
process leaves the page side doing the work.

The app's database is {database} The {toolchain} is already installed
here, so run the app straight from this checkout. Do not add
infrastructure and do not change how the app starts.

What the work has to keep:

- what the browser sees: same URLs, same requests, same responses and
  redirects, same markup — elements, classes, text. Pages stay
  server-rendered; no client-side rendering, no CSS or copy edits;
- rules: validation, permissions and reputation rules stay on the
  server, in the backend;
- data: whatever the old flow persisted is persisted the same way;
- the rest of the app: everything that works today still works.

Run it before calling it done; a clean compile is not evidence. Start
the app, call each new endpoint directly — a good request, a rejected
one, a user who is not signed in — drive the flow through its pages and
compare with before, check the database, and show in the app's log that
serving those pages makes requests to the backend. Report what you ran,
what it returned, and what you could only check by reading.

The repository's AGENTS.md describes the app and its toolchain.
