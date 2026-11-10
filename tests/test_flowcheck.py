"""Tests for forge-secure/flowcheck.py (the deeper pass: input that reaches a dangerous call, missing
access checks, uploads, weak crypto, mass assignment, secrets in logs)."""

import ast
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # also lets "-m unittest tests.test_flowcheck" work
from _load import ROOT, load, run_cp1252, symlink  # noqa: E402

flowcheck = load("forge-secure", "flowcheck")
codecheck = load("forge-secure", "codecheck")
SCRIPT = os.path.join(ROOT, "forge-secure", "flowcheck.py")
DATA = os.path.join(ROOT, "forge-secure", "flows.json")
ACCESS = "flow-no-access-check"
PHP = "<?php\n"

# (language, the rule ids expected, code). Each sample is a small file.
RISKY = [
    # --- request input that reaches a dangerous call
    ("python", "flow-sql", 'def v(request):\n    q = request.GET["q"]\n    cursor.execute("SELECT 1 FROM t WHERE a = \'%s\'" % q)\n'),
    ("python", "flow-sql", 'def v(request):\n    q = request.GET["q"]\n    sql = "SELECT 1 FROM t WHERE a = " + q\n    cursor.execute(sql)\n'),
    ("python", "flow-sql", 'def v(request):\n    rows = Item.objects.raw("SELECT 1 FROM t WHERE a = %s" % request.GET["q"])\n'),
    ("python", "flow-shell", 'def v():\n    name = request.args.get("name")\n    os.system("convert " + name)\n'),
    ("python", "flow-path", 'def v():\n    name = request.args["f"]\n    path = os.path.join(BASE, name)\n    return open(path).read()\n'),
    ("python", "flow-path", 'def v():\n    return send_file(request.args["f"])\n'),
    ("python", "flow-ssrf", 'def v(request):\n    url = request.POST.get("url")\n    r = requests.get(url, timeout=5)\n'),
    ("python", "flow-ssrf", 'def v(request):\n    host = request.GET["host"]\n    url = "https://" + host + "/status"\n    return requests.get(url)\n'),
    ("python", "flow-ssrf", 'def v():\n    data = request.get_json()\n    target = data["url"]\n    return requests.get(target).text\n'),
    ("python", "flow-redirect", 'def v(request):\n    nxt = request.GET.get("next")\n    return redirect(nxt)\n'),
    ("python", "flow-redirect", 'def v(request):\n    return HttpResponseRedirect(request.GET["next"])\n'),
    ("python", "flow-raw-html", 'def v(request):\n    name = request.GET.get("name")\n    return HttpResponse("<h1>Hi " + name + "</h1>")\n'),
    ("python", "flow-raw-html", 'def v():\n    tpl = request.form["tpl"]\n    return render_template_string(tpl)\n'),
    ("python", "flow-deserialise", 'def v():\n    blob = request.data\n    obj = jsonpickle.decode(blob)\n'),
    ("js", "flow-ssrf", 'export async function POST(req) {\n  const { url } = await req.json();\n  const res = await fetch(url);\n}\n'),
    ("js", "flow-ssrf", 'app.get("/p", async (req, res) => {\n  const r = await axios.get(req.query.url);\n});\n'),
    ("js", "flow-path", 'app.get("/f", (req, res) => {\n  const name = req.query.name;\n  res.sendFile(path.join(DIR, name));\n});\n'),
    ("js", "flow-redirect", 'app.get("/go", (req, res) => {\n  const next = req.query.next;\n  res.redirect(next);\n});\n'),
    ("js", "flow-redirect", 'export async function GET(request) {\n  const { searchParams } = new URL(request.url);\n'
                            '  const to = searchParams.get("to");\n  return NextResponse.redirect(to);\n}\n'),
    ("js", "flow-raw-html", 'const q = new URLSearchParams(location.search).get("q");\nel.innerHTML = q;\n'),
    ("js", "flow-raw-html", 'app.get("/hi", (req, res) => {\n  const name = req.query.name;\n  res.send("<h1>" + name + "</h1>");\n});\n'),
    ("js", "flow-sql " + ACCESS, 'app.get("/u/:id", async (req, res) => {\n  const id = req.params.id;\n'
                                 '  const sql = "SELECT * FROM users WHERE id = " + id;\n  const rows = await db.query(sql);\n});\n'),
    ("js", "flow-shell", 'app.post("/c", (req, res) => {\n  const file = req.body.file;\n  const cmd = "convert " + file;\n  exec(cmd);\n});\n'),
    ("js", "flow-deserialise", 'app.post("/c", (req, res) => {\n  const code = req.body.code;\n  vm.runInNewContext(code);\n});\n'),
    ("php", "flow-sql", PHP + 'function show(Request $request) {\n    $id = $request->input("id");\n'
                              '    $rows = DB::select("select * from users where id = $id");\n}\n'),
    ("php", "flow-shell", PHP + '$host = $_GET["host"];\n$out = shell_exec("ping -c 1 " . $host);\n'),
    ("php", "flow-path", PHP + '$page = $_GET["page"];\ninclude "pages/" . $page . ".php";\n'),
    ("php", "flow-path", PHP + 'function dl(Request $request) {\n    $name = $request->query("file");\n'
                               '    return response()->download(storage_path("docs/" . $name));\n}\n'),
    ("php", "flow-ssrf", PHP + 'function f(Request $request) {\n    $url = $request->input("url");\n    $r = Http::get($url);\n}\n'),
    ("php", "flow-ssrf", PHP + '$url = $_POST["url"];\n$ch = curl_init($url);\n'),
    ("php", "flow-redirect", PHP + 'function f(Request $request) {\n    return redirect($request->input("next"));\n}\n'),
    ("php", "flow-redirect", PHP + '$to = $_GET["to"];\nheader("Location: " . $to);\n'),
    ("php", "flow-raw-html", PHP + '$name = $request->input("name");\necho "<p>" . $name . "</p>";\n'),
    ("php", "flow-deserialise", PHP + '$cart = $_COOKIE["cart"];\n$items = unserialize($cart);\n'),
    # --- a record used by its id with no sign of a login or owner check
    ("python", ACCESS, 'def detail(request, pk):\n    order = Order.objects.get(pk=pk)\n    return render(request, "o.html", {"o": order})\n'),
    ("python", ACCESS, '@app.route("/orders/<int:order_id>")\ndef show(order_id):\n    order = Order.query.get_or_404(order_id)\n'
                       '    return jsonify(order.as_dict())\n'),
    ("python", ACCESS, '@router.get("/items/{item_id}")\nasync def read(item_id: int, db: Session = Depends(get_db)):\n'
                       '    return db.get(Item, item_id)\n'),
    ("js", ACCESS, 'export async function GET(req, { params }) {\n  const post = await prisma.post.findUnique({ where: { id: params.id } });\n'
                   '  return Response.json(post);\n}\n'),
    ("js", ACCESS, '"use server";\n\nexport async function deletePost(id) {\n  await prisma.post.delete({ where: { id } });\n}\n'),
    ("js", ACCESS, 'router.delete("/posts/:id", async (req, res) => {\n  await Post.findByIdAndDelete(req.params.id);\n  res.sendStatus(204);\n});\n'),
    ("php", ACCESS, PHP + 'class PostController extends Controller {\n    public function show($id) {\n'
                          '        $post = Post::findOrFail($id);\n        return view("post", compact("post"));\n    }\n}\n'),
    ("php", ACCESS, PHP + 'class PostController extends Controller {\n    public function update(Request $request, Post $post) {\n'
                          '        $post->update($request->only(["title"]));\n        return back();\n    }\n}\n'),
    # --- uploads
    ("php", "flow-upload-unchecked", PHP + 'function up(Request $request) {\n    $path = $request->file("doc")->store("docs");\n}\n'),
    ("php", "flow-upload-client-name", PHP + 'function up(Request $request) {\n    $request->validate(["doc" => "mimes:pdf|max:2048"]);\n'
                                             '    $file = $request->file("doc");\n    $file->storeAs("docs", $file->getClientOriginalName());\n}\n'),
    ("php", "flow-upload-client-name flow-upload-unchecked",
     PHP + 'move_uploaded_file($_FILES["f"]["tmp_name"], "uploads/" . $_FILES["f"]["name"]);\n'),
    ("python", "flow-upload-client-name flow-upload-unchecked",
     '@app.route("/up", methods=["POST"])\ndef up():\n    f = request.files["doc"]\n    f.save(os.path.join(UPLOADS, f.filename))\n'),
    ("js", "flow-upload-unchecked", 'export async function POST(req) {\n  const data = await req.formData();\n  const file = data.get("file");\n'
                                    '  const bytes = Buffer.from(await file.arrayBuffer());\n  await writeFile(`./uploads/${randomUUID()}`, bytes);\n}\n'),
    ("js", "flow-upload-client-name", 'const storage = multer.diskStorage({\n  filename: (req, file, cb) => cb(null, file.originalname),\n});\n'
                                      'const upload = multer({ storage, limits: { fileSize: 1e6 } });\n'),
    # --- weak crypto and tokens
    ("python", "flow-weak-hash", "digest = hashlib.md5(password.encode()).hexdigest()\n"),
    ("python", "flow-weak-hash", 'PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]\n'),
    ("js", "flow-weak-hash", 'const hash = crypto.createHash("sha1").update(password).digest("hex");\n'),
    ("php", "flow-weak-hash", PHP + "$token = md5($email . time());\n"),
    ("php", "flow-weak-hash", PHP + '$h = hash("sha1", $password);\n'),
    ("python", "flow-weak-random", 'token = "".join(random.choice(ALPHABET) for _ in range(32))\n'),
    ("python", "flow-weak-random", "order_id = random.randint(1, 10 ** 9)\n"),
    ("js", "flow-weak-random", "const resetCode = Math.floor(Math.random() * 1000000);\n"),
    ("js", "flow-weak-random", "const id = Math.random().toString(36).slice(2);\n"),
    ("php", "flow-weak-random", PHP + "$otp = mt_rand(100000, 999999);\n"),
    ("php", "flow-weak-random", PHP + "$id = uniqid();\n"),
    ("python", "flow-jwt-unverified", 'claims = jwt.decode(tok, options={"verify_signature": False})\n'),
    ("js", "flow-jwt-unverified", "const user = jwt.decode(token);\n"),
    ("js", "flow-jwt-unverified", 'jwt.verify(token, key, { algorithms: ["none"] });\n'),
    ("php", "flow-jwt-unverified", PHP + '$header = ["alg" => "none", "typ" => "JWT"];\n'),
    ("python", "flow-weak-cipher", "cipher = AES.new(key, AES.MODE_ECB)\n"),
    ("python", "flow-weak-cipher", 'iv = b"0000000000000000"\n'),
    ("js", "flow-weak-cipher", 'const c = crypto.createCipheriv("aes-128-ecb", key, null);\n'),
    ("php", "flow-weak-cipher", PHP + '$out = openssl_encrypt($data, "aes-256-ecb", $key);\n'),
    ("php", "flow-tls-off", PHP + "curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);\n"),
    ("php", "flow-tls-off", PHP + "$r = Http::withoutVerifying()->get($api);\n"),
    ("python", "flow-tls-off", "ctx = ssl._create_unverified_context()\n"),
    ("js", "flow-tls-off", "request({ url, strictSSL: false });\n"),
    # --- mass assignment
    ("php", "flow-mass-assign", PHP + "$user = User::create($request->all());\n"),
    ("python", "flow-mass-assign", "user = User.objects.create(**request.data)\n"),
    ("js", "flow-mass-assign", 'export async function POST(req) {\n  const body = await req.json();\n'
                               '  const user = await prisma.user.create({ data: body });\n}\n'),
    ("js", "flow-mass-assign", 'app.post("/u", async (req, res) => {\n  const user = await User.create(req.body);\n});\n'),
    # --- secrets in logs
    ("python", "flow-log-secret", 'logger.info("login %s %s", username, password)\n'),
    ("python", "flow-log-secret", 'print(f"token: {token}")\n'),
    ("js", "flow-log-secret", 'console.log("headers", req.headers);\n'),
    ("php", "flow-log-secret", PHP + 'Log::info("login", ["password" => $password]);\n'),
]

# Code that looks alike but is fine: a sanitiser on the way, a sign of an access check, the safe form of a call.
SAFE = [
    ("python", 'def v(request):\n    q = request.GET["q"]\n    cursor.execute("SELECT 1 FROM t WHERE name = %s", [q])\n'),
    ("python", 'def v(request):\n    q = int(request.GET["q"])\n    cursor.execute("SELECT 1 FROM t WHERE a = %s" % q)\n'),
    ("python", 'def v():\n    name = request.args.get("name")\n    subprocess.run(["convert", name])\n'),
    ("python", 'def v():\n    name = request.args["f"]\n    name = secure_filename(name)\n    return open(os.path.join(BASE, name)).read()\n'),
    ("python", 'def v(request):\n    uid = request.POST.get("id")\n    r = requests.get(f"{API}/users/{uid}", timeout=5)\n'),
    ("python", 'def v(request):\n    name = request.POST.get("name")\n    r = requests.post(API, json={"name": name})\n'),
    ("python", 'def v(request):\n    url = request.POST.get("url")\n    if urlparse(url).hostname not in ALLOWED_HOSTS:\n'
               '        abort(400)\n    r = requests.get(url, timeout=5)\n'),
    ("python", 'def v(request):\n    pk = request.GET.get("id")\n    return redirect(f"/items/{pk}")\n'),
    ("python", 'def v(request):\n    form = F(request.POST)\n    if not form.is_valid():\n        return\n'
               '    url = request.POST["url"]\n    requests.get(url)\n'),
    ("python", 'def a(request):\n    url = request.POST["url"]\n\ndef b(request, url):\n    requests.get(url)\n'),  # another function
    ("python", 'def v(request):\n    url = request.POST["url"]\n    url = settings.API_URL\n    requests.get(url)\n'),  # a new value
    ("js", 'app.get("/p", async (req, res) => {\n  const page = req.query.page;\n  const r = await fetch(`${API}/items?page=${page}`);\n});\n'),
    ("js", 'app.get("/f", (req, res) => {\n  const name = path.basename(req.query.name);\n  res.sendFile(path.join(DIR, name));\n});\n'),
    ("js", 'app.get("/u", requireAuth, async (req, res) => {\n  const id = req.params.id;\n'
           '  const rows = await db.query("SELECT * FROM users WHERE id = $1", [id]);\n});\n'),
    ("js", 'app.get("/go", (req, res) => {\n  const next = req.query.next;\n  if (!next.startsWith("/")) return res.sendStatus(400);\n'
           '  res.redirect(next);\n});\n'),
    ("php", PHP + 'function show(Request $request) {\n    $id = $request->input("id");\n'
                  '    $rows = DB::select("select * from users where id = ?", [$id]);\n}\n'),
    ("php", PHP + 'function show(Request $request) {\n    $id = intval($request->input("id"));\n'
                  '    $rows = DB::select("select * from users where id = $id");\n}\n'),
    ("php", PHP + '$host = $_GET["host"];\n$out = shell_exec("ping -c 1 " . escapeshellarg($host));\n'),
    ("php", PHP + '$type = $_GET["type"];\nheader("Content-Type: text/" . $type);\n'),
    ("php", PHP + 'function f(Request $request) {\n    $request->validate(["url" => "required|url"]);\n'
                  '    $url = $request->input("url");\n    $r = Http::get($url);\n}\n'),
    ("python", '@login_required\ndef detail(request, pk):\n    order = Order.objects.get(pk=pk)\n    return render(request, "o.html", {"o": order})\n'),
    ("python", 'def detail(request, pk):\n    order = Order.objects.get(pk=pk, user=request.user)\n    return render(request, "o.html", {})\n'),
    ("python", 'def helper(pk):\n    return Order.objects.get(pk=pk)\n'),  # not a handler
    ("python", 'def detail(request, slug):\n    return render(request, "e.html", {"e": get_object_or_404(Event, slug=slug)})\n'),
    ("php", PHP + 'function export(Request $request) {\n    $name = "posts." . $request->input("format");\n'
                  '    return response()->streamDownload(fn () => print(Post::all()->toJson()), $name);\n}\n'),
    ("python", '@app.route("/orders/<int:order_id>")\n@login_required\ndef show(order_id):\n    return Order.query.get_or_404(order_id)\n'),
    ("python", '@router.get("/items/{item_id}")\nasync def read(item_id: int, user=Depends(get_current_user)):\n    return db.get(Item, item_id)\n'),
    ("python", 'class V(APIView):\n    permission_classes = [IsAuthenticated]\n\n    def get(self, request, pk):\n'
               '        return Response(S(get_object_or_404(Order, pk=pk)).data)\n'),
    ("js", 'export async function GET(req, { params }) {\n  const session = await getServerSession(authOptions);\n'
           '  if (!session) return new Response(null, { status: 401 });\n'
           '  const post = await prisma.post.findUnique({ where: { id: params.id } });\n  return Response.json(post);\n}\n'),
    ("js", '"use server";\n\nexport async function deletePost(id) {\n  const session = await auth();\n'
           '  await prisma.post.delete({ where: { id, authorId: session.user.id } });\n}\n'),
    ("js", 'router.delete("/posts/:id", requireAuth, async (req, res) => {\n  await Post.findByIdAndDelete(req.params.id);\n});\n'),
    ("js", 'function load(id) {\n  return prisma.post.findUnique({ where: { id } });\n}\n'),  # not a handler
    ("php", PHP + 'class PostController extends Controller {\n    public function show($id) {\n        $post = Post::findOrFail($id);\n'
                  '        $this->authorize("view", $post);\n        return view("post", compact("post"));\n    }\n}\n'),
    ("php", PHP + 'class PostController extends Controller {\n    public function __construct() {\n        $this->middleware("auth");\n    }\n'
                  '    public function show($id) {\n        return Post::findOrFail($id);\n    }\n}\n'),
    ("php", PHP + 'class PostController extends Controller {\n    public function update(UpdatePostRequest $request, Post $post) {\n'
                  '        $post->update($request->validated());\n    }\n}\n'),
    ("php", PHP + 'class PostRepo {\n    public function byId($id) {\n        return Post::find($id);\n    }\n}\n'),  # not a controller
    ("php", PHP + 'function up(Request $request) {\n    $request->validate(["doc" => "required|mimes:pdf|max:2048"]);\n'
                  '    $path = $request->file("doc")->store("docs");\n}\n'),
    ("python", '@app.route("/up", methods=["POST"])\ndef up():\n    f = request.files["doc"]\n    if not allowed_file(f.filename):\n'
               '        abort(400)\n    f.save(os.path.join(UPLOADS, secure_filename(f.filename)))\n'),
    ("js", 'const upload = multer({ dest: "up/", limits: { fileSize: 1e6 }, fileFilter });\n'),
    ("python", "etag = hashlib.md5(body).hexdigest()\n"),
    ("python", "digest = hashlib.sha256(token.encode()).hexdigest()\n"),
    ("js", 'const etag = crypto.createHash("md5").update(body).digest("hex");\n'),
    ("php", PHP + "$etag = md5($content);\n"),
    ("python", "token = secrets.token_urlsafe(32)\n"),
    ("python", "delay = random.random() * 2\n"),
    ("js", "const x = Math.random() * width;\n"),
    ("js", "const token = crypto.randomUUID();\n"),
    ("php", PHP + "$key = array_rand($items);\n"),
    ("php", PHP + "$token = bin2hex(random_bytes(32));\n"),
    ("python", 'claims = jwt.decode(tok, KEY, algorithms=["HS256"])\n'),
    ("js", 'const user = jwt.verify(token, SECRET, { algorithms: ["HS256"] });\n'),
    ("python", "iv = os.urandom(16)\n"),
    ("python", 'nonce = "abc123"\n'),  # a CSP nonce in a test, not a cipher
    ("js", 'const c = crypto.createCipheriv("aes-256-gcm", key, crypto.randomBytes(12));\n'),
    ("php", PHP + "curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, true);\n"),
    ("php", PHP + "$user = User::create($request->validated());\n"),
    ("python", "user = User.objects.create(**serializer.validated_data)\n"),
    ("js", 'export async function POST(req) {\n  const body = schema.parse(await req.json());\n'
           '  const user = await prisma.user.create({ data: body });\n}\n'),
    ("python", 'logger.info("password reset requested for %s", user.pk)\n'),
    ("python", 'logger.info("used %d tokens", usage.total_tokens)\n'),
    ("js", 'console.error("Failed to verify token", err);\n'),
    ("php", PHP + 'Log::info("Password changed for user " . $user->id);\n'),
]

# What codecheck.py already reports: flowcheck.py must stay quiet on these lines (no rule twice).
CODECHECK_HAS = [
    ("php", "$hash = md5($password);"),
    ("python", "requests.get(url, verify=False)"),
    ("python", "claims = jwt.decode(tok, verify=False)"),
    ("js", "https.request({ host, rejectUnauthorized: false });"),
    ("php", "$rows = mysqli_query($db, \"SELECT * FROM users WHERE id = \" . $_GET['id']);"),
    ("php", "system(\"ping -c 1 \" . $_GET['host']);"),
    ("php", "echo \"Hello \" . $_GET['name'];"),
    ("php", "$cart = unserialize($_COOKIE['cart']);"),
    ("python", "obj = pickle.loads(request.body)"),
    ("python", "config = yaml.load(request.body)"),
    ("js", "exec(baseCmd + req.query.file);"),
]


def found(language, code):
    return flowcheck.scan_text(code, language, "sample")


def rule_ids(language, code):
    return sorted({item["rule"] for item in found(language, code)})


def make_tree(root, files):
    """Write {relative path: text or bytes} under root."""
    for rel, content in files.items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(content if isinstance(content, bytes) else content.encode("utf-8"))


def run_main(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = flowcheck.main(list(args))
        except SystemExit as exit_error:  # argparse errors and --help
            code = exit_error.code
    return code, out.getvalue(), err.getvalue()


class RuleTests(unittest.TestCase):
    def test_each_risky_sample_hits_exactly_its_rules(self):
        for language, rules, code in RISKY:
            with self.subTest(code=code):
                self.assertEqual(rule_ids(language, code), sorted(rules.split()))

    def test_safe_samples_are_not_flagged(self):
        for language, code in SAFE:
            with self.subTest(code=code):
                self.assertEqual(rule_ids(language, code), [])

    def test_every_check_in_the_rule_file_has_a_risky_sample(self):
        with open(DATA, encoding="utf-8") as handle:
            data = json.load(handle)
        wanted = {(check["rule"], check["lang"]) for check in data["checks"]}
        sampled = {(rule, language) for language, rules, _ in RISKY for rule in rules.split()}
        self.assertEqual(wanted - sampled, set())
        self.assertEqual({rule for rule, _ in wanted}, set(data["rules"]), "a rule with no check, or a check with no rule")

    def test_severities(self):
        expected = {"flow-sql": "critical", "flow-shell": "critical", "flow-path": "high", "flow-ssrf": "high",
                    "flow-redirect": "medium", "flow-raw-html": "high", "flow-deserialise": "high", ACCESS: "high",
                    "flow-upload-unchecked": "medium", "flow-upload-client-name": "high", "flow-weak-hash": "medium",
                    "flow-weak-random": "high", "flow-jwt-unverified": "high", "flow-weak-cipher": "medium",
                    "flow-tls-off": "high", "flow-mass-assign": "high", "flow-log-secret": "medium"}
        with open(DATA, encoding="utf-8") as handle:
            rules = json.load(handle)["rules"]
        self.assertEqual({rule: info["severity"] for rule, info in rules.items()}, expected)
        for info in rules.values():
            for key in ("title", "why", "fix"):
                self.assertTrue(info[key].strip())

    def test_two_checks_are_milder_than_their_rule(self):
        self.assertEqual([f["severity"] for f in found("js", "const id = Math.random().toString(36);\n")], ["medium"])
        self.assertEqual([f["severity"] for f in found("js", "const resetToken = Math.random().toString(36);\n")], ["high"])
        laravel = found("php", PHP + "$user = User::create($request->all());\n")
        self.assertEqual([f["severity"] for f in laravel], ["medium"])  # Laravel guards models unless $guarded is emptied
        self.assertIn("$fillable", laravel[0]["title"])

    def test_access_check_is_worded_as_a_check(self):
        item = found("python", "def detail(request, pk):\n    return Order.objects.get(pk=pk)\n")[0]
        self.assertTrue(item["title"].startswith("Check that"))
        self.assertEqual((item["severity"], item["line"]), ("high", 2))

    def test_a_finding_names_the_variable_and_where_it_came_from(self):
        code = 'def v(request):\n\n    url = request.POST.get("url")\n    log(url)\n    return requests.get(url)\n'
        item = found("python", code)[0]
        self.assertEqual((item["rule"], item["where"], item["file"], item["line"]), ("flow-ssrf", "sample:5", "sample", 5))
        self.assertIn("(url, line 3)", item["title"])
        for key in ("severity", "why", "fix"):
            self.assertTrue(item[key])

    def test_it_does_not_repeat_codecheck(self):
        for language, line in CODECHECK_HAS:
            with self.subTest(line=line):
                self.assertTrue(codecheck.scan_text(line, language, "x"), "codecheck.py no longer reports this")
                self.assertEqual(rule_ids(language, line), [])

    def test_rules_only_apply_to_their_own_language(self):
        self.assertEqual(rule_ids("python", "const resetCode = Math.random();\n"), [])
        self.assertEqual(rule_ids("js", "token = random.choice(ALPHABET)\n"), [])


class FlowTests(unittest.TestCase):
    def test_a_value_is_followed_for_forty_lines(self):
        head = 'def v(request):\n    url = request.GET["u"]\n'
        self.assertEqual(rule_ids("python", head + "    x = 1\n" * 30 + "    requests.get(url)\n"), ["flow-ssrf"])
        self.assertEqual(rule_ids("python", head + "    x = 1\n" * 45 + "    requests.get(url)\n"), [])

    def test_a_call_over_several_lines(self):
        code = ('app.get("/u", requireAuth, async (req, res) => {\n  const name = req.query.name;\n  const rows = await db.query(\n'
                '    `SELECT * FROM users\n     WHERE name = \'${name}\'`\n  );\n});\n')
        self.assertEqual([(f["rule"], f["line"]) for f in found("js", code)], [("flow-sql", 3)])

    def test_a_copy_of_a_copy_is_followed_but_not_further(self):
        code = ('def v():\n    data = request.get_json()\n    host = data["host"]\n    url = "https://" + host\n'
                '    return requests.get(url)\n')
        self.assertEqual(rule_ids("python", code), ["flow-ssrf"])
        code = code.replace("return requests.get(url)", 'final = url + "/x"\n    return requests.get(final)')
        self.assertEqual(rule_ids("python", code), [])

    def test_a_value_that_does_not_pick_the_host_is_not_ssrf(self):
        code = 'def v(request):\n    name = request.GET["name"]\n    url = f"{settings.API}/users/{name}"\n    return requests.get(url)\n'
        self.assertEqual(rule_ids("python", code), [])

    def test_a_record_fetched_by_id_is_not_followed(self):
        code = 'def v(request):\n    pk = request.GET["id"]\n    item = Item.objects.get(pk=pk, owner=request.user)\n    return redirect(item.url)\n'
        self.assertEqual(rule_ids("python", code), [])

    def test_one_finding_per_function_for_scope_checks(self):
        code = ('def a(request, pk):\n    x = Order.objects.get(pk=pk)\n    y = Line.objects.filter(order_id=pk)\n\n\n'
                '@login_required\ndef b(request, pk):\n    return Order.objects.get(pk=pk)\n\n\n'
                'def c(request, pk):\n    return Order.objects.get(pk=pk)\n')
        self.assertEqual([(f["rule"], f["line"]) for f in found("python", code)], [(ACCESS, 2), (ACCESS, 12)])

    def test_opt_out(self):
        self.assertEqual(rule_ids("js", "const user = jwt.decode(token); // forge:allow shown only\n"), [])
        code = 'def v(request):\n    nxt = request.GET.get("next")\n    return redirect(nxt)  # forge:allow\n'
        self.assertEqual(rule_ids("python", code), [])
        code = "def detail(request, pk):  # forge:allow the router checks the login\n    return Order.objects.get(pk=pk)\n"
        self.assertEqual(rule_ids("python", code), [])
        self.assertEqual(rule_ids("python", code.replace("forge:allow", "note")), [ACCESS])

    def test_old_mac_and_windows_line_ends(self):
        code = 'def v(request):\r    nxt = request.GET.get("next")\r\n    return redirect(nxt)\r'
        self.assertEqual([f["line"] for f in found("python", code)], [3])

    def test_long_lines_are_read_up_to_the_limit(self):
        self.assertEqual(rule_ids("js", "const user = jwt.decode(token);" + " " * 3000), ["flow-jwt-unverified"])
        self.assertEqual(rule_ids("js", " " * 3000 + "const user = jwt.decode(token);"), [])

    def test_pathological_input_stays_fast(self):
        tokens = ["request.GET ", "$x = $_GET['a'] . ", "fetch(", "put(file.name ", "{ id ", ".format(", "Http::a()->", "`${",
                  "const { a, b } = req.body; ", "x = request.GET['x']\n", "A" * 50, "prisma.user.create({ data ", "(\n", '"',
                  "console.log(", "def v(request):\n    Order.objects.get(pk=pk)\n", "function ($a) { Post::find($id); }\n"]
        for token in tokens:
            text = (token * (60000 // len(token) + 1))[:60000]
            for language in ("php", "python", "js"):
                with self.subTest(token=token, language=language):
                    start = time.time()
                    flowcheck.scan_text(text, language, "x")
                    self.assertLess(time.time() - start, 10)

    def test_the_pack_does_not_flag_its_own_scripts(self):
        # A copy of the skill in a project's .claude/skills/ must not fail that project's security gate.
        code, out, _ = run_main(os.path.join(ROOT, "forge-secure"), "--json")
        self.assertEqual((code, json.loads(out)["findings"]), (0, []))


class RuleFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rules = os.path.join(self.tmp.name, "flows.json")
        self.code = os.path.join(self.tmp.name, "ok.py")
        make_tree(self.tmp.name, {"ok.py": "print('hello')\n"})

    def run_with(self, text):
        if text is not None:
            with open(self.rules, "w", encoding="utf-8") as handle:
                handle.write(text)
        with mock.patch.object(flowcheck, "DATA", self.rules), mock.patch.dict(flowcheck.CACHE, clear=True):
            return run_main(self.code)

    def test_a_missing_or_broken_rule_file_is_exit_2(self):
        with open(DATA, encoding="utf-8") as handle:
            good = json.load(handle)
        no_fix = json.loads(json.dumps(good))
        no_fix["rules"]["flow-sql"]["fix"] = " "
        bad_pattern = json.loads(json.dumps(good))
        bad_pattern["checks"][0]["pattern"] = "("
        unknown = json.loads(json.dumps(good))
        unknown["checks"][0]["rule"] = "flow-nothing"
        for text in (None, "{not json", "[]", "{}", json.dumps(no_fix), json.dumps(bad_pattern), json.dumps(unknown)):
            with self.subTest(text=(text or "missing")[:20]):
                code, out, err = self.run_with(text)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("missing or broken", err)
        self.assertEqual(self.run_with(json.dumps(good))[0], 0)

    def test_the_rule_file_is_plain_data(self):
        with open(DATA, encoding="utf-8") as handle:
            text = handle.read()
        data = json.loads(text)
        self.assertEqual(set(data), {"about", "rules", "blanket", "languages", "checks"})
        self.assertEqual(set(data["languages"]), {"php", "python", "js"})
        self.assertTrue(all(ord(char) < 128 for char in text), "ASCII only")
        self.assertEqual({check["kind"] for check in data["checks"]}, {"sink", "line", "scope"})


class FolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def wheres(self, path):
        return sorted(f["where"] for f in json.loads(run_main(path, "--json")[1])["findings"])

    def test_skipped_folders_and_unknown_file_types(self):
        risky = "const user = jwt.decode(token);\n"
        files = {name + "/lib/x.js": risky for name in flowcheck.SKIP_DIRS}
        files.update({"src/app.js": risky, "notes.txt": risky, "src/framework/ok.ts": risky, "views/a.vue": risky})
        make_tree(self.root, files)
        self.assertEqual(self.wheres(self.root), ["src/app.js:1", "src/framework/ok.ts:1", "views/a.vue:1"])
        self.assertTrue(codecheck.SKIP_DIRS < flowcheck.SKIP_DIRS)  # codecheck's list, and forge-work
        self.assertEqual(flowcheck.SKIP_DIRS - codecheck.SKIP_DIRS, {"forge-work"})
        self.assertEqual((flowcheck.LANGUAGES, flowcheck.MAX_BYTES), (codecheck.LANGUAGES, codecheck.MAX_BYTES))

    def test_binary_and_big_files_are_listed_as_skipped(self):
        make_tree(self.root, {"image.js": b"\x89PNG\0\0jwt.decode(t)\n", "big.py": "x = 1\n" * 200000, "ok.js": "jwt.decode(t);\n"})
        code, out, _ = run_main(self.root, "--json")
        data = json.loads(out)
        self.assertEqual((code, [f["where"] for f in data["findings"]]), (1, ["ok.js:1"]))
        self.assertEqual(data["summary"]["files_skipped"], ["big.py", "image.js"])
        self.assertIn("Skipped (binary or over 1 MB): big.py, image.js", run_main(self.root)[1])

    def test_symlinks_are_not_followed(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        make_tree(outside.name, {"evil.js": "jwt.decode(t);\n", "dir/inner.js": "jwt.decode(t);\n"})
        symlink(self, os.path.join(outside.name, "evil.js"), os.path.join(self.root, "link.js"))
        symlink(self, os.path.join(outside.name, "dir"), os.path.join(self.root, "linkdir"))
        self.assertEqual(self.wheres(self.root), [])

    def test_unreadable_file_makes_the_scan_incomplete(self):
        make_tree(self.root, {"a.js": "jwt.decode(t);\n", "b.py": "print(y)\n"})
        real_open = open

        def flaky_open(path, *args, **kwargs):
            if str(path).endswith("a.js"):
                raise PermissionError(13, "Permission denied")
            return real_open(path, *args, **kwargs)

        with mock.patch.object(flowcheck, "open", flaky_open, create=True):
            code, out, _ = run_main(self.root, "--json")
            human = run_main(self.root, "--fail-on", "critical")
        data = json.loads(out)
        self.assertEqual((code, data["findings"]), (2, []), "an incomplete scan never looks clean")
        self.assertEqual(data["summary"]["unreadable"], [{"path": "a.js", "reason": "Permission denied"}])
        self.assertTrue(data["summary"]["incomplete"])
        self.assertEqual(human[0], 2)
        self.assertIn("INCOMPLETE, so not a pass. Could not read: a.js (Permission denied)", human[1])

    def test_unreadable_subfolder_is_listed_and_exit_2(self):
        make_tree(self.root, {"locked/a.js": "jwt.decode(t);\n", "open/b.js": "jwt.decode(t);\n"})
        locked, real_scandir = os.path.join(self.root, "locked"), os.scandir

        def scandir(path="."):
            if os.path.abspath(path) == os.path.abspath(locked):
                raise PermissionError(13, "Permission denied", path)
            return real_scandir(path)

        with mock.patch("os.scandir", scandir):
            code, out, _ = run_main(self.root, "--json")
        data = json.loads(out)
        self.assertEqual((code, [f["where"] for f in data["findings"]]), (2, ["open/b.js:1"]))
        self.assertEqual(data["summary"]["unreadable"], [{"path": "locked", "reason": "Permission denied"}])


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        make_tree(self.root, {
            "views.py": 'def v(request):\n    q = request.GET["q"]\n    cursor.execute("SELECT 1 FROM t WHERE a = \'%s\'" % q)\n'
                        '    return redirect(request.GET["next"])\n',  # critical on line 3, medium on line 4
            "only_medium.py": "cipher = AES.new(key, AES.MODE_ECB)\n",
            "only_high.js": "const user = jwt.decode(token);\n",
            "clean.py": "print('hello')\n",
        })

    def path(self, name):
        return os.path.join(self.root, name)

    def test_human_output(self):
        code, out, _ = run_main(self.path("views.py"))
        self.assertEqual(code, 1)
        self.assertLess(out.index("CRITICAL  Request input (q, line 2) is pasted into a database query [flow-sql]"),
                        out.index("MEDIUM  Request input (request.GET, line 4) decides where"), "worst first")
        self.assertIn("          where: " + self.path("views.py") + ":3", out)
        self.assertIn("          why:   ", out)
        self.assertIn("        fix:   ", out)
        self.assertIn("2 findings: 1 critical, 1 medium.", out)
        self.assertIn("Files checked: 1", out)
        self.assertIn("heuristic", out)

    def test_clean_file_and_singular(self):
        code, out, _ = run_main(self.path("clean.py"))
        self.assertEqual(code, 0)
        self.assertIn("No findings.", out)
        self.assertIn("1 finding: 1 high.", run_main(self.path("only_high.js"))[1])

    def test_json_output_shape(self):
        code, out, _ = run_main(self.root, "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(sorted(data), ["findings", "note", "summary"])
        self.assertEqual([f["severity"] for f in data["findings"]], ["critical", "high", "medium", "medium"])
        for item in data["findings"]:
            self.assertEqual(sorted(item), ["file", "fix", "line", "rule", "severity", "title", "where", "why"])
        summary = data["summary"]
        self.assertEqual((summary["total"], summary["critical"], summary["high"], summary["medium"], summary["low"]),
                         (4, 1, 1, 2, 0))
        self.assertEqual((summary["files_checked"], summary["files_skipped"], summary["unreadable"], summary["incomplete"]),
                         (4, [], [], False))
        self.assertIn("heuristic", data["note"])

    def test_fail_on(self):
        self.assertEqual(run_main(self.path("only_medium.py"))[0], 0)
        self.assertEqual(run_main(self.path("only_medium.py"), "--fail-on", "medium")[0], 1)
        self.assertEqual(run_main(self.path("only_medium.py"), "--fail-on", "low")[0], 1)
        self.assertEqual(run_main(self.path("only_high.js"))[0], 1)
        self.assertEqual(run_main(self.path("only_high.js"), "--fail-on", "critical")[0], 0)
        self.assertEqual(run_main(self.path("clean.py"), "--fail-on", "low")[0], 0)

    def test_bad_input_is_exit_2(self):
        code, out, err = run_main(self.path("nope"))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("does not exist", err)
        make_tree(self.root, {"readme.txt": "x\n", "big.py": "x = 1\n" * 200000, "image.js": b"\0\0x\n"})
        for name in ("readme.txt", "big.py", "image.js"):
            with self.subTest(name=name):
                code, out, err = run_main(self.path(name))
                self.assertEqual((code, out), (2, ""))
                self.assertIn("error: ", err)
        self.assertEqual(run_main(os.devnull)[0], 2)
        self.assertEqual(run_main(self.root, "--fail-on", "urgent")[0], 2)
        self.assertEqual(run_main()[0], 2)

    def test_unreadable_file_is_exit_2(self):
        with mock.patch.object(flowcheck, "open", side_effect=PermissionError(13, "Permission denied"), create=True), \
                mock.patch.dict(flowcheck.CACHE, flowcheck.rules()):
            code, out, _ = run_main(self.path("clean.py"))
        self.assertEqual(code, 2)
        self.assertIn("INCOMPLETE, so not a pass.", out)
        self.assertNotIn("No findings.", out)

    def test_folder_with_nothing_to_check_says_so(self):
        make_tree(self.root, {"go/main.go": "package main\n"})
        code, out, _ = run_main(self.path("go"))
        self.assertEqual(code, 0)
        self.assertIn("Nothing was checked", out)
        self.assertNotIn("No findings", out)

    def test_help_and_runs_as_a_script(self):
        code, out, _ = run_main("--help")
        self.assertEqual(code, 0)
        for words in ("Usage:", "Exit codes:", "--fail-on", "forge:allow", "heuristic"):
            self.assertIn(words, out)
        done = subprocess.run([sys.executable, SCRIPT, self.path("only_high.js"), "--json"], capture_output=True, timeout=120)
        self.assertEqual(done.returncode, 1)
        self.assertEqual(json.loads(done.stdout)["summary"]["high"], 1)

    def test_output_into_a_closed_pipe_ends_quietly(self):
        with open(self.path("many.js"), "w") as handle:
            handle.write("const user = jwt.decode(token);\n" * 5000)
        done = subprocess.Popen([sys.executable, SCRIPT, self.root], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        done.stdout.close()  # the reader is gone before anything is printed
        error = done.stderr.read().decode()
        done.stderr.close()
        self.assertEqual(done.wait(timeout=60), 1)
        self.assertNotIn("Traceback", error)

    def test_a_cp1252_pipe_gets_escapes_not_a_crash(self):
        make_tree(self.root, {"sub/café →.js": "const user = jwt.decode(token);\n"})
        code, out, err = run_cp1252(SCRIPT, self.path("sub"))
        self.assertEqual(code, 1, err)
        self.assertIn("where: café \\u2192.js:1", out)


class ConventionTests(unittest.TestCase):
    def setUp(self):
        with open(SCRIPT, encoding="utf-8") as handle:
            self.source = handle.read()

    def test_docstring_length_and_imports(self):
        for words in ("Usage", "Exit codes", "forge:allow", "heuristic", "not a data-flow engine", "one variable name",
                      "flows.json", "codecheck.py"):
            self.assertIn(words, flowcheck.__doc__)
        self.assertLessEqual(len(self.source.splitlines()), 300)
        imports = sorted(line for line in self.source.splitlines() if line.startswith(("import ", "from ")))
        self.assertEqual(imports, ["import argparse", "import errno", "import json", "import os", "import re", "import sys"])

    def test_python_3_9_and_docstrings(self):
        tree = ast.parse(self.source, feature_version=(3, 9))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name != "cannot_open":
                self.assertTrue(ast.get_docstring(node), node.name)


if __name__ == "__main__":
    unittest.main()
