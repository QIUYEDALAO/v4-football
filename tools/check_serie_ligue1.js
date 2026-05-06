const https = require("https");
const zlib = require("zlib");
const vm = require("vm");

function fetchDecompressed(url) {
  return new Promise((resolve, reject) => {
    https.get(url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate",
      },
      timeout: 20000,
    }, (res) => {
      const chunks = [];
      const encoding = res.headers["content-encoding"] || "";
      if (encoding.includes("gzip")) {
        const gunzip = zlib.createGunzip();
        res.pipe(gunzip);
        gunzip.on("data", c => chunks.push(c));
        gunzip.on("end", () => resolve(Buffer.concat(chunks)));
        gunzip.on("error", reject);
      } else {
        res.on("data", c => chunks.push(c));
        res.on("end", () => resolve(Buffer.concat(chunks)));
      }
    }).on("error", reject).on("timeout", function() { this.destroy(); reject(new Error("timeout")); });
  });
}

async function main() {
  const buf = await fetchDecompressed("https://live.nowscore.com/data/bf.js?" + Date.now());
  let raw = buf.toString("utf-8");
  
  let code = raw.replace(/ShowBf\(\);?\s*$/, "");
  code = code.replace(/\bShowBf\s*\(\)/g, "0")
    .replace(/^var\s+(A|B|C)\s*=\s*Array\(/gm, "globalThis.$1=Array(")
    .replace(/^var\s+(matchcount|sclasscount|countrycount|matchdate)\s*=/gm, "globalThis.$1=")
    .replace(/^A\[(\d+)\]=/gm, "globalThis.A[$1]=")
    .replace(/^B\[(\d+)\]=/gm, "globalThis.B[$1]=")
    .replace(/^C\[(\d+)\]=/gm, "globalThis.C[$1]=");
  
  const ctx = vm.createContext({A:[],B:[],C:[]});
  vm.runInContext(code, ctx, { timeout: 5000 });
  
  const sname = {};
  for (const b of ctx.B) {
    if (b && Array.isArray(b)) sname[b[0]] = b[1];
  }
  
  // 意甲 sclassId=34/1, 法甲 sclassId=11
  // Let me check all sclassIds that match
  const targetIds = {};
  for (const key of Object.keys(sname)) {
    const name = sname[key];
    if (name.includes("意甲") || name.includes("法甲")) {
      targetIds[key] = name;
    }
  }

  // Find in-progress matches
  console.log("意甲/法甲 — 进行中比赛:\n");
  for (let i = 0; i < ctx.A.length; i++) {
    const m = ctx.A[i];
    if (!Array.isArray(m)) continue;
    const sid = String(m[1]);
    const name = targetIds[sid];
    if (!name) continue;
    if (m[12] !== 3) continue;
    
    const leagueName = sname[m[1]] || `#${m[1]}`;
    const ht = `${m[16]}-${m[17]}`;
    const ft = `${m[14]}-${m[15]}`;
    console.log(`${leagueName}`);
    console.log(`  ${m[4]} ${ft} ${m[7]}`);
    console.log(`  半场: ${ht} | ${m[31]}分钟`);
    console.log(`  盘口: ${m[25] ?? "-"}`);
    console.log(`  matchId: ${m[0]}`);
    
    const totalHt = (m[16]||0) + (m[17]||0);
    if (totalHt >= 1) {
      console.log(`  上半场进球: ${totalHt}球 ✅`);
    } else {
      console.log(`  上半场: 0-0 ❌`);
    }
    console.log("");
  }

  // Check all in-progress matches for comparison
  const allLive = ctx.A.filter(m => Array.isArray(m) && m[12] === 3);
  console.log(`\n全部进行中比赛 (${allLive.length}场):`);
  for (const m of allLive) {
    const name = sname[m[1]] || `#${m[1]}`;
    console.log(`  ${name}: ${m[4]} ${m[14]}-${m[15]} ${m[7]} | ${m[31]}分钟 | ht:${m[16]}-${m[17]}`);
  }
}

main().catch(e => console.error(e.message));
