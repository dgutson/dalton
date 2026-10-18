// Compile every <script> block in index.html without running it. Catches the syntax
// errors the quickjs tests cannot: they only execute the sliced pure-computation
// region, so anything touching the DOM has never been through a parser.
import * as std from "qjs:std";
const html = std.loadFile("/data/data/com.termux/files/home/src/dalton/index.html");
const re = /<script\b[^>]*>([\s\S]*?)<\/script>/gi;
let m, n = 0;
while((m = re.exec(html)) !== null){
  const body = m[1];
  if(!body.trim()) continue;
  n++;
  const line = html.slice(0, m.index).split('\n').length;
  try { new Function(body); }
  catch(e){ print('FAIL  script starting at line ' + line + ': ' + e); std.exit(1); }
}
if(!n){ print('FAIL  no <script> block found — did the file change shape?'); std.exit(1); }
print('ok    ' + n + ' script block' + (n>1?'s':'') + ' compile');
