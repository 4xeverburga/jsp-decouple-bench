This app renders its pages on the server and reads the database from the
process that serves them.

The job is to split the whole app along two edges at once.

The browser edge: pages stop arriving rendered. The browser is given data
as JSON and builds the markup itself.

The server edge: the code that builds those pages stops reading the
database. It reaches the app's own JSON endpoints over HTTP — a request
to the address and port the browser already uses — instead of calling
data-access code (a DAO, a repository, a database session) directly. The
queries have not gone away; they moved behind the endpoint.

That call has to be a real request over the wire: a URL, a response, and
the data coming back through it. Passing the same objects across in
memory, invoking the endpoint's method directly, or forwarding the
request inside the process leaves the page code still holding the
database, which is the thing this edge exists to end.

Both edges are the job, and answering one is not doing it: serving JSON
while the page code still holds the database leaves the data side inside
the page build, and moving the queries behind an endpoint while still
answering with HTML leaves the browser edge where it was.

The app's database is {database} The {toolchain} is already installed
here, so run the app straight from this checkout. Do not add
infrastructure and do not change how the app starts.

What the work has to keep:

- addresses: pages keep their URLs, and the links between them keep
  working;
- rules: validation, permissions and reputation rules stay on the
  server;
- data: whatever the old flows persisted is persisted the same way, in
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
- check that the database holds afterwards what the old flows left
  there;
- load each page and check that its markup still has the elements,
  classes and text it had, and that the scripts it now loads are served;
- show the server edge happening: when a page is built, its requests to
  the app's own endpoints arrive over the wire, where the app's log or
  its access log can see them.

None of that runs your scripts, so check them against the pages by
reading: every selector a script uses has to exist in the markup it is
given, and what it builds has to match what the server used to render —
element for element, class for class. When you report, say what you
ran, what it returned, and what you could only check by reading.

The repository's AGENTS.md describes the app and its toolchain.
