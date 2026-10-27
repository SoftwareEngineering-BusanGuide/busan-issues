import type { WeatherGrid } from '../types'

/** 값이 다 채워진 격자. 바다처럼 관측이 없는 칸은 주변 육지 값으로 채운다 */
export interface FilledGrid {
  lats: number[]
  lngs: number[]
  temperature: number[][]
  u: number[][]
  v: number[][]
}

type Field = (number | null)[][]

/** 빈 칸을 관측값이 있는 칸들의 거리 가중 평균(IDW)으로 채운다 */
function fillField(field: Field): number[][] | null {
  const known: [number, number, number][] = []
  field.forEach((row, r) => row.forEach((value, c) => value != null && known.push([r, c, value])))
  if (known.length === 0) return null
  return field.map((row, r) =>
    row.map((value, c) => {
      if (value != null) return value
      let sum = 0
      let weights = 0
      for (const [kr, kc, kv] of known) {
        const w = 1 / ((kr - r) ** 2 + (kc - c) ** 2)
        sum += w * kv
        weights += w
      }
      return sum / weights
    }),
  )
}

export function fillGrid(grid: WeatherGrid): FilledGrid | null {
  const temperature = fillField(grid.temperature)
  const u = fillField(grid.u)
  const v = fillField(grid.v)
  if (!temperature || !u || !v) return null
  return { lats: grid.lats, lngs: grid.lngs, temperature, u, v }
}

/** 격자 사이를 이중선형 보간한다. 격자 밖은 가장자리 값으로 */
export function sample(values: number[][], lats: number[], lngs: number[], lat: number, lng: number): number {
  const fi = Math.min(Math.max(((lat - lats[0]) / (lats[lats.length - 1] - lats[0])) * (lats.length - 1), 0), lats.length - 1)
  const fj = Math.min(Math.max(((lng - lngs[0]) / (lngs[lngs.length - 1] - lngs[0])) * (lngs.length - 1), 0), lngs.length - 1)
  const i0 = Math.floor(fi)
  const j0 = Math.floor(fj)
  const i1 = Math.min(i0 + 1, lats.length - 1)
  const j1 = Math.min(j0 + 1, lngs.length - 1)
  const ti = fi - i0
  const tj = fj - j0
  const top = values[i0][j0] * (1 - tj) + values[i0][j1] * tj
  const bottom = values[i1][j0] * (1 - tj) + values[i1][j1] * tj
  return top * (1 - ti) + bottom * ti
}

/** 기온 색 (℃ → RGB). 애플 날씨와 비슷하게 차가울수록 보라·파랑, 따뜻할수록 노랑·빨강 */
export const TEMPERATURE_STOPS: [number, [number, number, number]][] = [
  [-40, [91, 33, 182]],
  [-20, [37, 99, 235]],
  [0, [56, 189, 248]],
  [10, [52, 211, 153]],
  [20, [250, 204, 21]],
  [30, [249, 115, 22]],
  [55, [185, 28, 28]],
]

export function temperatureColor(t: number): [number, number, number] {
  const stops = TEMPERATURE_STOPS
  if (t <= stops[0][0]) return stops[0][1]
  for (let k = 1; k < stops.length; k++) {
    const [t1, c1] = stops[k]
    if (t <= t1) {
      const [t0, c0] = stops[k - 1]
      const f = (t - t0) / (t1 - t0)
      return [0, 1, 2].map((n) => Math.round(c0[n] + (c1[n] - c0[n]) * f)) as [number, number, number]
    }
  }
  return stops[stops.length - 1][1]
}

/** 기온 면 이미지를 그린다 (지도 bounds 전체를 덮는 PNG data URL) */
export function renderTemperatureImage(
  grid: FilledGrid,
  bounds: [[number, number], [number, number]],
  width = 180,
  height = 160,
): string {
  const [[west, south], [east, north]] = bounds
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')!
  const image = ctx.createImageData(width, height)
  for (let y = 0; y < height; y++) {
    const lat = north - ((y + 0.5) / height) * (north - south)
    for (let x = 0; x < width; x++) {
      const lng = west + ((x + 0.5) / width) * (east - west)
      const [r, g, b] = temperatureColor(sample(grid.temperature, grid.lats, grid.lngs, lat, lng))
      const k = (y * width + x) * 4
      image.data[k] = r
      image.data[k + 1] = g
      image.data[k + 2] = b
      image.data[k + 3] = 255
    }
  }
  ctx.putImageData(image, 0, 0)
  return canvas.toDataURL()
}

/** 바람이 불어오는 방향(도) → 16방위 */
export function windDirectionName(deg: number): string {
  const names = ['북', '북북동', '북동', '동북동', '동', '동남동', '남동', '남남동', '남', '남남서', '남서', '서남서', '서', '서북서', '북서', '북북서']
  return names[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16]
}
