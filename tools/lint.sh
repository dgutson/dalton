#!/data/data/com.termux/files/usr/bin/bash
# Static checks for a single-file app with no build step. Catches the mistakes that
# actually happen here: a reference to something that was deleted, an element id that
# does not exist, an unbalanced edit. Run after EVERY edit to index.html.
#
# It will not catch logic errors. For those, run tools/check.sh, which executes the
# real code against real captures.
cd "$(dirname "$0")/.."
python3 - "$@" <<'PY'
import io, re, sys, ast, os

bad = 0
s = io.open('index.html', encoding='utf-8').read()
js = s[s.index('<script>')+8 : s.rindex('</script>')]

# strip comments first, then strings — an apostrophe inside a comment is not a string
out=[]; i=0; n=len(js)
while i < n:
    c = js[i]
    if c=='/' and i+1<n and js[i+1]=='/':
        while i<n and js[i]!='\n': i+=1
        continue
    if c=='/' and i+1<n and js[i+1]=='*':
        i = js.index('*/', i)+2; continue
    if c in '"\'`':
        q=c; i+=1
        while i<n and js[i]!=q:
            if js[i]=='\\': i+=1
            i+=1
        i+=1; out.append(' S '); continue
    out.append(c); i+=1
clean = ''.join(out)

st=[]; pairs={')':'(',']':'[','}':'{'}; line=1
for ch in clean:
    if ch=='\n': line+=1
    elif ch in '([{': st.append((ch,line))
    elif ch in ')]}':
        if not st or st[-1][0]!=pairs[ch]:
            print('FAIL  unbalanced %r at line %d' % (ch,line)); bad=1; break
        st.pop()
else:
    if st: print('FAIL  never closed: %s' % st[:3]); bad=1
if not bad: print('ok    brackets balanced')

ids = set(re.findall(r'id="([^"]+)"', s))
miss = sorted({m.group(1) for m in re.finditer(r"\$\('([^']+)'\)", js)} - ids)
print('FAIL  $() on missing element id: %s' % miss if miss else 'ok    every $() id exists')
bad |= bool(miss)

defined = set(re.findall(r'function\s+([A-Za-z_$][\w$]*)', clean))
for g in re.findall(r'(?:const|let|var)\s+([^=;{]+?)[=;]', clean):
    defined |= {x.strip() for x in g.split(',') if x.strip().isidentifier()}
called = set(re.findall(r'(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(', clean))
KW = set('if for while switch catch function return typeof new delete void async do else'.split())
BUILTIN = set('''Math JSON Number String Array Object Promise Error Map Set Date
Uint8Array Uint32Array Int32Array Float32Array TextEncoder SpeechSynthesisUtterance
parseInt parseFloat isNaN setTimeout requestAnimationFrame fetch addEventListener
performance'''.split())
ghosts = sorted(called - defined - KW - BUILTIN)
print('FAIL  called but never defined: %s' % ghosts if ghosts else 'ok    no ghost references')
bad |= bool(ghosts)

for f in ['serve.py'] + sorted('tools/'+x for x in os.listdir('tools') if x.endswith('.py')):
    try:
        ast.parse(io.open(f).read()); print('ok    %s parses' % f)
    except SyntaxError as e:
        print('FAIL  %s line %s: %s' % (f, e.lineno, e.msg)); bad=1

sys.exit(bad)
PY

# The quickjs tests only execute the sliced pure-computation region, so everything
# that touches the DOM has never been near a parser. Compile it without running it.
qjs --std tools/parse_test.js
