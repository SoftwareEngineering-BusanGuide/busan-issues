import type maplibregl from 'maplibre-gl'
import { windColor } from '../../lib/constants'
import { sample, type FilledGrid } from '../../lib/weatherField'

/** 한 프레임에 움직이는 화면 픽셀 = PIXEL_SCALE × √풍속 (확대 수준과 관계없이 같은 속도로 보이게).
 * 제곱근을 써서 약한 바람(1~3m/s)도 흐름이 선으로 보이고, 강한 바람은 너무 빨라지지 않게 한다 */
const PIXEL_SCALE = 1.5
const FADE = 0.965 // 이전 프레임을 이만큼 남겨 긴 꼬리를 만든다

interface Particle {
  lng: number
  lat: number
  age: number
  maxAge: number
}

/**
 * 지도 위 캔버스에 바람 입자를 흘려 보낸다 (애플 날씨 '바람' 레이어 방식).
 * 입자는 지리 좌표로 두고 매 프레임 화면 좌표로 바꿔 움직이므로, 지도를 움직여도 바람 위치가 맞는다.
 * 움직임 줄이기 설정이면 애니메이션 없이 짧은 흐름선만 한 번 그린다. 반환값을 호출하면 멈춘다.
 */
export function startWindParticles(map: maplibregl.Map, canvas: HTMLCanvasElement, grid: FilledGrid): () => void {
  const ctx = canvas.getContext('2d')!
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const dpr = window.devicePixelRatio || 1
  let particles: Particle[] = []
  let frame = 0
  let stopped = false

  const velocity = (lng: number, lat: number) => ({
    u: sample(grid.u, grid.lats, grid.lngs, lat, lng),
    v: sample(grid.v, grid.lats, grid.lngs, lat, lng),
  })

  const resize = () => {
    const { clientWidth: w, clientHeight: h } = map.getContainer()
    canvas.width = Math.round(w * dpr)
    canvas.height = Math.round(h * dpr)
    canvas.style.width = `${w}px`
    canvas.style.height = `${h}px`
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }

  const spawn = (p?: Particle): Particle => {
    const b = map.getBounds()
    const particle = p ?? { lng: 0, lat: 0, age: 0, maxAge: 0 }
    particle.lng = b.getWest() + Math.random() * (b.getEast() - b.getWest())
    particle.lat = b.getSouth() + Math.random() * (b.getNorth() - b.getSouth())
    particle.age = 0
    particle.maxAge = 80 + Math.floor(Math.random() * 80)
    return particle
  }

  const reset = () => {
    resize()
    const { clientWidth: w, clientHeight: h } = map.getContainer()
    const count = Math.min(1800, Math.round((w * h) / 700))
    particles = Array.from({ length: count }, () => spawn())
    // 처음부터 나이를 흩어 놓아 한꺼번에 사라졌다 생기지 않게 한다
    particles.forEach((p) => (p.age = Math.floor(Math.random() * p.maxAge)))
    ctx.clearRect(0, 0, canvas.width, canvas.height)
  }

  const drawSegment = (p: Particle, length: number) => {
    const { u, v } = velocity(p.lng, p.lat)
    const speed = Math.hypot(u, v)
    const from = map.project([p.lng, p.lat])
    const scale = speed > 0.01 ? (PIXEL_SCALE * Math.sqrt(speed) * length) / speed : 0
    // 화면 y는 아래로 갈수록 커지므로 북쪽 성분(v)은 빼 준다
    const to = { x: from.x + u * scale, y: from.y - v * scale }
    ctx.strokeStyle = windColor(speed)
    ctx.beginPath()
    ctx.moveTo(from.x, from.y)
    ctx.lineTo(to.x, to.y)
    ctx.stroke()
    return to
  }

  const step = () => {
    if (stopped) return
    // 이전 프레임을 조금씩 지워 꼬리가 남게 한다
    ctx.globalCompositeOperation = 'destination-in'
    ctx.fillStyle = `rgba(0, 0, 0, ${FADE})`
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.globalCompositeOperation = 'source-over'
    ctx.lineWidth = 1.3
    ctx.globalAlpha = 0.9

    const { clientWidth: w, clientHeight: h } = map.getContainer()
    for (const p of particles) {
      if (p.age++ > p.maxAge) {
        spawn(p)
        continue
      }
      const to = drawSegment(p, 1)
      if (to.x < 0 || to.y < 0 || to.x > w || to.y > h) {
        spawn(p)
        continue
      }
      const next = map.unproject([to.x, to.y])
      p.lng = next.lng
      p.lat = next.lat
    }
    frame = requestAnimationFrame(step)
  }

  // 움직임 줄이기: 애니메이션 없이 흐름선만 한 번
  const drawStatic = () => {
    resize()
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.lineWidth = 1.2
    ctx.globalAlpha = 0.8
    const { clientWidth: w, clientHeight: h } = map.getContainer()
    const count = Math.min(900, Math.round((w * h) / 1200))
    for (let i = 0; i < count; i++) drawSegment(spawn(), 15)
  }

  // 지도를 움직이는 동안 이전 꼬리가 엉뚱한 곳에 남지 않도록 지운다
  const clear = () => ctx.clearRect(0, 0, canvas.width, canvas.height)
  const onMoveEnd = () => (reduceMotion ? drawStatic() : reset())

  map.on('movestart', clear)
  map.on('moveend', onMoveEnd)
  map.on('resize', onMoveEnd)
  if (reduceMotion) {
    drawStatic()
  } else {
    reset()
    frame = requestAnimationFrame(step)
  }

  return () => {
    stopped = true
    cancelAnimationFrame(frame)
    map.off('movestart', clear)
    map.off('moveend', onMoveEnd)
    map.off('resize', onMoveEnd)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
  }
}
