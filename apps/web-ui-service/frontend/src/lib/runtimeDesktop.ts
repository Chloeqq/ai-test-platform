export function buildRuntimeDesktopUrl(): string {
  const current = new URL(window.location.href);
  current.protocol = "http:";
  current.port = "6080";
  current.pathname = "/vnc.html";
  current.search = "autoconnect=1&resize=scale";
  current.hash = "";
  return current.toString();
}

