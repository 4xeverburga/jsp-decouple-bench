Users need to post an answer to a question. Today the form posts to a server-rendered page and the browser navigates. Make the submit answer with JSON and let the page update itself from that response.

What to add: a controller action that takes the answer the form already sends and replies with JSON — the answer's body and author, and the question's answer count — plus a client-side script on the question page that posts the form, appends the answer to the list and updates the count. Reproducing today's markup from that response is the job; a script that does it is not a new component.

What must stay: the server's validation, permissions and persistence; the page's address; every other flow; and what a browser sees for an answer and for the count — the same elements, classes and text as today. No CSS, no copy changes, no new visual elements, no reordering.

Byte-identical HTML is neither required nor possible once the browser builds the new answer: the page still arrives rendered on first load, and only the submit changes. Equal elements, classes and text is the bar.

Done means: submitting the form gets JSON back instead of a page, so the address does not change and nothing reloads; the script appends the answer to the list and raises the count from that response; and loading the question page again shows the same answer and count, because the server persisted them. When that holds, stop.
