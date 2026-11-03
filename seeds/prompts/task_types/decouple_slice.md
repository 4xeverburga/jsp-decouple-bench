This app renders its pages on the server: the controllers build them and
the views come back as HTML.

The job is to separate the two. For the part of the app described below,
the backend should serve what a screen needs as JSON and the browser
should render it.

The app's database is {database} The {toolchain} is already installed
here, so run the app straight from this checkout. Do not add
infrastructure and do not change how the app starts.

What the work has to keep:

- addresses: pages keep their URLs, and the links between them keep
  working;
- rules: validation, permissions and reputation rules stay on the
  server — JavaScript never becomes the authority;
- data: whatever the old flow persisted is persisted the same way, in
  the same place;
- the page itself: the markup does not change. Same elements, same
  classes, same text as today, so what a user — or a browser
  automation driving one — sees is identical before and after. This is
  plumbing, not a redesign: no new components, no CSS or copy edits, no
  reordering;
- the rest of the app: everything that works today still works.

Run it before calling it done. A clean compile is not evidence. There is
no browser here, so the evidence is what you can reach over HTTP:

- start the app against the database and let it finish booting;
- call every endpoint you added or changed and read what comes back —
  the JSON a good request gets, and what a bad one gets: a rejected
  form, a user who is not signed in;
- check that the database holds afterwards what the old flow left there;
- load the page the flow starts on and check that its markup still has
  the elements, classes and text it had, and that the script it now
  loads is served.

None of that runs your script, so check it against the page by reading:
every selector it uses has to exist in the markup it is given, and what
it builds has to match what the server used to render — element for
element, class for class. When you report, say what you ran, what it
returned, and what you could only check by reading.

The repository's AGENTS.md describes the app and its toolchain.
