/* Demo deployment: mounts the captured workspace snapshot as the API layer. */
window.MS_SNAPSHOT = null;
fetch("/api-snapshot.json").then(r => r.json()).then(d => {
  window.MS_SNAPSHOT = d;
  document.dispatchEvent(new Event("snapshot-ready"));
});
