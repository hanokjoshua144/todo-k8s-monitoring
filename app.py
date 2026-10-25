import os, sys, json, socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = os.environ.get("APP_VERSION", "v1")
if "crash" in VERSION:            # simulates a buggy release that dies on startup
    print("FATAL: simulated startup failure", flush=True)
    sys.exit(1)

POD = socket.gethostname()
TODOS = []                        # in-memory (per pod) - deliberate limitation, see report

PAGE = """<!doctype html><html><head><title>Team To-Do</title></head>
<body style="font-family:sans-serif;max-width:560px;margin:40px auto">
<h2>Team To-Do <small style="color:#888">__VERSION__</small></h2>
<p style="color:#555">Served by pod: <b>__POD__</b></p>
<input id="t" placeholder="New task"><button onclick="add()">Add</button>
<ul id="l"></ul>
<script>
async function load(){const r=await fetch('/api/todos');const d=await r.json();
document.getElementById('l').innerHTML=d.map(x=>'<li>'+x+'</li>').join('')}
async function add(){const v=document.getElementById('t').value;if(!v)return;
await fetch('/api/todos',{method:'POST',body:JSON.stringify({task:v})});
document.getElementById('t').value='';load()}
load()
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html"):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/healthz":
            self._send(200, "ok", "text/plain")
        elif self.path == "/api/todos":
            self._send(200, json.dumps(TODOS), "application/json")
        else:
            self._send(200, PAGE.replace("__VERSION__", VERSION).replace("__POD__", POD))

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        TODOS.append(json.loads(self.rfile.read(n))["task"])
        self._send(201, "{}", "application/json")

    def log_message(self, fmt, *a):
        print(f"[{VERSION}][{POD}] {self.address_string()} {fmt % a}", flush=True)

print(f"Starting todo app {VERSION} on pod {POD}", flush=True)
ThreadingHTTPServer(("", 8080), H).serve_forever()
