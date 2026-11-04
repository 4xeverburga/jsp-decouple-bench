Users need to post an answer to a question. Today the controller behind the answer form saves the answer itself, and the question page it redirects to reads the question and its answers the same way.

Add backend endpoints for that work: one that takes what the form already sends, validates and saves it, and returns the answer and the question's answer count; one that returns what the question page is rendered from. Then have both page-side controllers call them over HTTP and render the same views.

Done means: for the browser, submitting behaves exactly as before — same request, same redirect, same page, a rejected answer shown the same way; the answer and count on that page came from the backend, which the app's log shows; and reloading the page shows them again because the backend persisted them. When that holds, stop.
