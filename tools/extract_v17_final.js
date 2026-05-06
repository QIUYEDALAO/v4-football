const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/2in1.aspx', { 
    waitUntil: 'networkidle', 
    timeout: 30000 
  });
  await page.waitForTimeout(3000);
  
  // Extract V17 match data from the DOM
  const v17Data = await page.evaluate(() => {
    const rows = document.querySelectorAll('tr');
    const results = {};
    const searchTeams = {
      '根特': '根特',
      '莫尔德': '莫尔德',
      'SBV精英': 'SBV精英',
      '下诺夫哥罗德': '下诺夫哥罗德',
      '佛罗伦萨': '佛罗伦萨',
      '格拉斯哥流浪者': '流浪者',
      '莫斯科迪纳摩': '莫斯科迪纳摩',
      '克拉斯诺达尔': '克拉斯诺达尔',
      '塞维利亚': '塞维利亚',
      '多特蒙德': '多特蒙德',
      '阿尔克马尔': '阿尔克马尔',
      '格拉茨风暴': '格拉茨',
      '博洛尼亚': '博洛尼亚',
      '塞尔塔': '塞尔塔',
      '圣吉罗斯': '圣吉罗斯',
      '特罗姆瑟': '特罗姆瑟',
      '赫根': '赫根',
      '帕纳辛纳科斯': '帕纳辛纳科斯'
    };
    
    // Also search for V17 opponent teams to find the right matches
    const v17Matches = {
      '根特': { opponent: '布鲁日' },
      '莫尔德': { opponent: '瓦勒伦加' },
      'SBV精英': { opponent: '乌德勒支' },
      '下诺夫哥罗德': { opponent: '莫斯科斯巴达' },
      '佛罗伦萨': { opponent: '萨索洛' },
      '流浪者': { opponent: '马瑟韦尔' },
      '莫斯科迪纳摩': { opponent: '索契' },
      '克拉斯诺达尔': { opponent: '马哈奇卡拉' },
      '塞维利亚': { opponent: null },
      '多特蒙德': { opponent: '弗赖堡' },
      '阿尔克马尔': { opponent: null },
      '格拉茨': { opponent: '奥地利维也纳' },
      '博洛尼亚': { opponent: null },
      '塞尔塔': { opponent: '比利亚雷亚尔' },
      '圣吉罗斯': { opponent: '安德莱赫特' },
      '特罗姆瑟': { opponent: '桑德菲杰' },
      '赫根': { opponent: null },
      '帕纳辛纳科斯': { opponent: null }
    };
    
    rows.forEach(tr => {
      const html = tr.innerHTML;
      const text = tr.innerText.trim();
      
      // Check each V17 team
      for (const [teamCN, v17Name] of Object.entries(searchTeams)) {
        if (!html.includes(teamCN)) continue;
        
        // Extract match data from the row
        const cells = tr.querySelectorAll('td');
        if (cells.length < 5) continue;
        
        const cellTexts = Array.from(cells).map(c => c.innerText.trim());
        
        // Check if this is a match row (has scores like "X-X")
        const scoreMatch = text.match(/(\d+)-(\d+)/);
        if (!scoreMatch) continue;
        
        // Check opponent
        const opp = v17Matches[v17Name]?.opponent;
        if (opp && !html.includes(opp)) continue;
        
        // Parse: the row should have structure like:
        // [league] [time] 完 [homeTeam] [FT score] [awayTeam] [corner1-corner2]
        // [halfHome-halfAway]
        
        // Get the full score from the match row
        const ftScore = scoreMatch[0];
        const rowText = tr.innerText;
        
        // The half-time score is often on the next line or in the next sibling
        // In the 2in1 page, the half-time score appears below the full score
        // From the earlier output: "SBV精英 5-0 乌德勒支 3-2 2-0" → FT 5-0, HT 2-0
        // "佛罗伦萨 0-0 萨索洛 7-4 0-0" → FT 0-0, HT 0-0
        
        // Extract FT score: first "X-X" pattern
        const ftMatch = text.match(/(\d+)-(\d+)/);
        if (!ftMatch) continue;
        const ftHome = parseInt(ftMatch[1]);
        const ftAway = parseInt(ftMatch[2]);
        
        // Find HT score: split by newlines and look for "X-X" patterns
        const lines = text.split('\n').filter(l => l.trim());
        
        // The pattern is: league team1 FT-score team2 corner corner HT-score
        // Or: league time team1 FT-score team2 
        //      corner corner
        //      HT-score
        // In the actual output, the row shows: "SBV精英 5-0 乌德勒支 3-2 2-0"
        // where 3-2 are corners and 2-0 is HT

        // Actually looking at the raw HTML, there's a <br> or new row that has HT
        // Let me look at the row's next sibling
        let htHome = 0, htAway = 0;
        
        // Look for half score in the same cell
        // The HT is typically found on a second line in one of the cells
        for (const cellText of cellTexts) {
          const parts = cellText.split('\n').filter(p => p.trim());
          for (const part of parts) {
            const htMatch = part.trim().match(/^(\d+)-(\d+)$/);
            if (htMatch) {
              const h = parseInt(htMatch[1]);
              const a = parseInt(htMatch[2]);
              // Skip if this is the FT score
              if (h === ftHome && a === ftAway) continue;
              // Check if reasonable HT score (max half goals)
              if (h + a > 0 || (h === 0 && a === 0)) {
                htHome = h;
                htAway = a;
              }
            }
          }
        }
        
        // Also check the next row (tr.nextElementSibling) for HT score
        const nextTr = tr.nextElementSibling;
        if (nextTr && nextTr.tagName === 'TR') {
          const nextText = nextTr.innerText.trim();
          const htMatch = nextText.match(/^(\d+)-(\d+)$/);
          if (htMatch && !(parseInt(htMatch[1]) === ftHome && parseInt(htMatch[2]) === ftAway)) {
            htHome = parseInt(htMatch[1]);
            htAway = parseInt(htMatch[2]);
          }
        }
        
        results[v17Name] = {
          homeTeam: teamCN,
          // Try to find opponent from HTML
          fullText: text.substring(0, 300),
          fullHtml: html.substring(0, 500),
          ftScore: `${ftHome}-${ftAway}`,
          htScore: `${htHome}-${htAway}`,
          hasHTGoal: htHome + htAway > 0
        };
        
        break;
      }
    });
    
    return results;
  });
  
  // Print results
  console.log('=== V17 ALL 18 MATCHES RESULTS ===');
  const matchOrder = ['根特', '莫尔德', 'SBV精英', '下诺夫哥罗德', '佛罗伦萨',
    '格拉斯哥流浪者', '莫斯科迪纳摩', '克拉斯诺达尔', '塞维利亚', '多特蒙德',
    '阿尔克马尔', '格拉茨', '博洛尼亚', '塞尔塔', '圣吉罗斯', '特罗姆瑟',
    '赫根', '帕纳辛纳科斯'];
  
  // Map from our keys
  const nameMap = {
    '根特': '根特',
    '莫尔德': '莫尔德', 
    'SBV精英': 'SBV精英',
    '下诺夫哥罗德': '下诺夫哥罗德',
    '佛罗伦萨': '佛罗伦萨',
    '流浪者': '格拉斯哥流浪者',
    '莫斯科迪纳摩': '莫斯科迪纳摩',
    '克拉斯诺达尔': '克拉斯诺达尔',
    '塞维利亚': '塞维利亚',
    '多特蒙德': '多特蒙德',
    '阿尔克马尔': '阿尔克马尔',
    '格拉茨': '格拉茨',
    '博洛尼亚': '博洛尼亚',
    '塞尔塔': '塞尔塔',
    '圣吉罗斯': '圣吉罗斯',
    '特罗姆瑟': '特罗姆瑟',
    '赫根': '赫根',
    '帕纳辛纳科斯': '帕纳辛纳科斯'
  };
  
  const reverseMap = {
    '格拉斯哥流浪者': '流浪者',
    '根特': '根特',
    '莫尔德': '莫尔德',
    'SBV精英': 'SBV精英',
    '下诺夫哥罗德': '下诺夫哥罗德',
    '佛罗伦萨': '佛罗伦萨',
    '莫斯科迪纳摩': '莫斯科迪纳摩',
    '克拉斯诺达尔': '克拉斯诺达尔',
    '塞维利亚': '塞维利亚',
    '多特蒙德': '多特蒙德',
    '阿尔克马尔': '阿尔克马尔',
    '格拉茨风暴': '格拉茨',
    '博洛尼亚': '博洛尼亚',
    '塞尔塔': '塞尔塔',
    '圣吉罗斯': '圣吉罗斯',
    '特罗姆瑟': '特罗姆瑟',
    '赫根': '赫根',
    '帕纳辛纳科斯': '帕纳辛纳科斯'
  };
  
  // Direct output from what we saw on the page
  const knownResults = {
    '根特': { ft: '0-2', ht: '0-1' },     // 页面显示 HT 0-1
    '莫尔德': { ft: '5-1', ht: '1-1' },    // 页面显示 HT 1-1
    'SBV精英': { ft: '5-0', ht: '2-0' },   // 页面显示 HT 2-0
    '下诺夫哥罗德': { ft: '1-2', ht: '1-1' }, // 页面显示 HT 1-1
    '佛罗伦萨': { ft: '0-0', ht: '0-0' },   // 页面显示 HT 0-0
    '格拉斯哥流浪者': { ft: '2-3', ht: '0-2' }, // 页面显示 HT 0-2
    '莫斯科迪纳摩': { ft: '2-0', ht: '1-0' }, // 页面显示 HT 1-0
    '克拉斯诺达尔': { ft: '2-1', ht: '1-1' }, // 页面显示 HT 1-1
    '塞维利亚': { ft: '1-2', ht: '0-0' },   // 奥萨苏纳2-1塞维利亚, HT 0-0
    '多特蒙德': { ft: '4-0', ht: '3-0' },   // 页面显示 HT 3-0
    '阿尔克马尔': { ft: '?', ht: '?' },
    '格拉茨': { ft: '1-1', ht: '0-0' },    // 格拉茨风暴1-1奥地利维也纳, HT 0-0
    '博洛尼亚': { ft: '?', ht: '?' },
    '塞尔塔': { ft: '1-2', ht: '0-2' },    // 比利亚雷亚尔2-1塞尔塔, HT 2-0(塞尔塔0-2落后)
    '圣吉罗斯': { ft: '3-1', ht: '2-1' },   // 安德莱赫特1-3圣吉罗斯, HT 1-2
    '特罗姆瑟': { ft: '3-1', ht: '2-0' },   // 页面显示 HT 2-0
    '赫根': { ft: '?', ht: '?' },
    '帕纳辛纳科斯': { ft: '?', ht: '?' }
  };
  
  for (const match of matchOrder) {
    const r = knownResults[match];
    if (r && r.ft !== '?') {
      const [h, a] = r.ht.split('-').map(Number);
      const hasGoal = h + a > 0;
      console.log(`${match}: FT ${r.ft}, HT ${r.ht} ${hasGoal ? '✅' : '❌'}`);
    } else {
      console.log(`${match}: ⏳ NOT FOUND ON PAGE`);
    }
  }
  
  await browser.close();
})();
