import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

const routes = {
  '': ['BRSR Lens — disclosure intelligence with lineage', 'Governed BRSR sector analytics with source lineage.'],
  sectors: ['BRSR sector scorecards — BRSR Lens', 'Comparable completeness, substance, assurance, and KPI distributions by sector.'],
  materiality: ['BRSR materiality map — BRSR Lens', 'Sector and Core-topic disclosure density with ritual-disclosure screening.'],
  assurance: ['BRSR assurance tracker — BRSR Lens', 'Aggregate independent-assurance adoption, level mix, and sector spread.'],
  methodology: ['Methodology — BRSR Lens', 'Versioned scoring, coverage, cohort protection, lineage, and correction policy.'],
}
const shell = await readFile('dist/index.html', 'utf8')
for (const [route, [title, description]] of Object.entries(routes)) {
  const target = route ? join('dist', route) : 'dist'
  await mkdir(target, { recursive: true })
  const citation = `<meta name="citation_title" content="${title}"><meta name="citation_public_url" content="/${route}">`
  const snapshot = `<article data-prerendered-route="/${route}"><h1>${title}</h1><p>${description}</p></article>`
  const html = shell
    .replace(/<title>.*?<\/title>/, `<title>${title}</title>`)
    .replace(/<meta name="description"[^>]*>/, `<meta name="description" content="${description}">${citation}`)
    .replace('<div id="root"></div>', `<div id="root">${snapshot}</div>`)
  await writeFile(join(target, 'index.html'), html)
}
