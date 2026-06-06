// Drives the running dev server (localhost:5173) in a real Chromium and captures
// desktop (1440×900) scenario screenshots into docs/img/ for the README.
//   1) npm run dev   (in another terminal)
//   2) node scripts/shots.mjs
import { chromium } from 'playwright'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { mkdirSync } from 'node:fs'

const here = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(here, '../docs/img')
mkdirSync(OUT, { recursive: true })
const URL = process.env.URL || 'http://localhost:5173'

const browser = await chromium.launch({
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
})
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
const wait = (ms) => page.waitForTimeout(ms)
const shot = async (name) => { await page.screenshot({ path: resolve(OUT, name) }); console.log('✓', name) }

await page.goto(URL, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('.seg', { timeout: 20000 })
await wait(4500) // map tiles + WebGL layers (software GL is slower)

// helpers
const persona = (n) => page.locator('.persona button').nth(n).click()
const mode = (n) => page.locator('.seg button').nth(n).click()
const rankRow = (n) => page.locator('.rank__list .rank__row').nth(n).click()

// 1) 도시설계 · 가치 히트맵 (hero)
await shot('01-heatmap.png')

// 2) 가치 히트맵 클릭 → 적정가 + 왜 (InfoPanel). 강남·송파 핫스팟 부근 클릭.
await page.mouse.click(1040, 555)
await wait(900)
await shot('02-heatmap-click.png')

// 3) 현재 광고판 (적정성 색 overview)
await mode(1)
await wait(2200)
await shot('03-adstops.png')

// 4) 신설 후보 (랭킹 + 지도)
await mode(2)
await wait(2200)
await shot('04-candidates.png')

// 5) 신설 후보 1순위 클릭 → 카드 + 지도 이동 (삼성역)
await rankRow(0)
await wait(1800)
await shot('05-candidate-card.png')

// 6) 광고주 · 가성비 (랭킹) + 정류장 카드
await persona(1)
await wait(2200)
await rankRow(1)
await wait(1800)
await shot('06-advertiser-value.png')

// 7) 예산 플래너 + 관광·외국인 타겟 → 바구니
await mode(1) // 예산 플래너
await wait(800)
await page.locator('.target .chip', { hasText: '관광·외국인' }).click()
await wait(1800)
await shot('07-budget-tourist.png')

await browser.close()
console.log('done')
