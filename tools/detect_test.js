// Runs the REAL detector and namer out of index.html against a raw RGBA dump, under
// quickjs. This is the shipped code, sliced out by its own section markers — there is
// no second copy of the algorithm anywhere, so there is nothing that can drift.
//
//   qjs --std tools/detect_test.js <file.rgba> <w> <h> <strict|normal|loose> [simple]
import * as std from "qjs:std";
import * as os  from "qjs:os";

const html = std.loadFile("/data/data/com.termux/files/home/src/dalton/index.html");
// Slice the pure-computation region by its own markers, never by line number.
const A = html.indexOf("/* ---------- colour bands ---------- */");
const B = html.indexOf("/* ---------- state ---------- */");
if(A < 0 || B < 0 || B < A) throw new Error("markers moved in index.html");
const src = html.slice(A, B);

const stub = `
  var load = (k,d)=>d, save = ()=>{};
  var simple = SIMPLE_MODE;
  var bracketOn = false;
`;
const run = new Function("SIMPLE_MODE", stub + src + `
  return {detectBlobs, measureBlobs, TIER, MAX_LEDS};
`);


const argv = scriptArgs;
const raw = argv[1], W = +argv[2], H = +argv[3];
const tier = ({strict:'low', normal:'med', loose:'high'})[argv[4]] || argv[4];
const M = run(argv[5] === 'simple');
const f = std.open(raw, "rb");
const buf = new Uint8Array(W*H*4);
f.read(buf.buffer, 0, buf.length);
f.close();

const det = M.detectBlobs(buf, W, H, tier);
const out = M.measureBlobs([{data:buf, ev:0}], det, W, H);
print(JSON.stringify({
  T:det.T, Tloc:det.Tloc, peak:det.peak, frac:det.frac, nRaw:det.blobs.length,
  drop:out.drop,
  leds: out.kept.map(b=>{ const m=b.meas, src=m.pick.src; return {
          cx:Math.round(b.cx), cy:Math.round(b.cy), area:b.area,
          label:b.res.label, hue:b.res.hue===null?null:+b.res.hue.toFixed(1),
          kin:b.kin===undefined?null:+b.kin.toFixed(4),
          sure:b.res.sure, lowIso:!!b.lowIso, washed:m.pick.washed,
          sat: src?+src.sat.toFixed(3):null, conc: src?+src.conc.toFixed(3):null,
          nUse:m.a.nUse, nGray:m.a.nGray, nClip:m.a.nClip, nDark:m.a.nDark, nPix:m.a.n}; })
}));
