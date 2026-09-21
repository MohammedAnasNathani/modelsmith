
import sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
old_path = os.path.join(HERE, "app.demo.js")
src_path = os.path.join(HERE, "..", "frontend", "app.js")

old = open(old_path).read()
cur = open(src_path).read()

p1 = old.index("const SNAPSHOT_READY = ")
p1 = old.rfind("\n", 0, p1) + 1
p2 = old.index("function logoutLocal()")
demo_block = old[p1:p2]

banner = (
    '<div class="demo-banner">\n'
    '      <span class="demo-banner-dot"></span>\n'
    '      Sample workspace — sign in to work with the live backend\n'
    '      <span class="demo-banner-note">Runs, training and uploads need the backend running</span>\n'
    '      <a class="demo-banner-link" href="https://github.com/MohammedAnasNathani/modelsmith" target="_blank" rel="noopener">Source →</a>\n'
    '    </div>\n    '
)

v1 = old.index("function viewLogin(")
v2 = old.index("async function viewDashboard(")
demo_viewlogin = old[v1:v2]

out = cur
assert '<div class="bg-fx"></div>' in out, "bg-fx anchor missing from app.js"
out = out.replace('<div class="bg-fx"></div>',
                  '${API_BASE() ? "" : `' + banner.replace("`", "\\`") + '`}<div class="bg-fx"></div>', 1)
assert "function logoutLocal()" in out, "logoutLocal anchor missing"
out = out.replace("function logoutLocal()",
                  "window.MS_STATIC = true;\n" + demo_block + "function logoutLocal()", 1)


open(old_path, "w").write(out)
print(f"app.demo.js rebuilt: {len(out)} bytes")
