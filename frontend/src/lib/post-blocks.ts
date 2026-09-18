// 글 1건을 네이버 에디터에 넣을 형태로 준비하는 공용 함수.
// 예전에는 확장이 브라우저 안에서 했지만, 지금은 여기서 만들어 서버 큐에 담고
// PC 실행기가 순서대로 삽입한다. 저장글 화면과 원클릭 발행이 같은 규칙을 쓴다.

export interface PostBlock { type: 'text' | 'image'; content?: string; image?: string }

// 본문에서 자동 강조할 키워드(반복 단어) 추출 — 조사 제거 + 불용어 제외 + 빈도순
const _JOSA = ['으로써','으로서','이라고','라고','에서는','에서도','으로','에서','에게','한테','부터','까지','처럼','같이','마다','조차','밖에','이나','라도','이란','은','는','이','가','을','를','에','와','과','도','만','의','로']
const _STOP = new Set(['그리고','그러나','하지만','그래서','또한','또는','그런데','때문','위해','통해','대해','경우','정도','우리','여러분','있습니다','합니다','입니다','습니다','됩니다','있는','하는','되는','매우','정말','너무','아주','가장','모든','다양한','오늘','안녕하세요','감사합니다'])
function stripJosa(w: string): string {
  if (!/[가-힣]$/.test(w)) return w
  for (const j of _JOSA) if (w.endsWith(j) && w.length - j.length >= 2) return w.slice(0, -j.length)
  return w
}
export function extractKeywords(text: string, topN = 6): string[] {
  const counts = new Map<string, number>()
  const words = (text || '').match(/[가-힣A-Za-z0-9]+/g) || []
  for (const raw of words) {
    const w = stripJosa(raw)
    if (w.length < 2 || _STOP.has(w) || /^[0-9]+$/.test(w)) continue
    counts.set(w, (counts.get(w) || 0) + 1)
  }
  const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1])
  const repeated = sorted.filter(([, c]) => c >= 2).map(([w]) => w)
  return repeated.slice(0, topN)
}

// 본문을 문단으로 나눠 이미지를 고르게 끼운 블록(글-이미지-글-이미지)
export function buildInterleavedBlocks(content: string, images: string[]): PostBlock[] {
  const text = (content || '').replace(/\r\n/g, '\n').trim()
  let paras = text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean)
  if (paras.length <= 1) paras = text.split(/\n/).map((p) => p.trim()).filter(Boolean)
  if (paras.length === 0) paras = [text || '']
  const n = images.length
  const blocks: PostBlock[] = []
  let imgIdx = 0
  for (let p = 0; p < paras.length; p++) {
    blocks.push({ type: 'text', content: paras[p] })
    const upto = Math.round(((p + 1) * n) / paras.length)
    while (imgIdx < upto) { blocks.push({ type: 'image', image: images[imgIdx] }); imgIdx++ }
  }
  while (imgIdx < n) { blocks.push({ type: 'image', image: images[imgIdx] }); imgIdx++ }
  return blocks
}
