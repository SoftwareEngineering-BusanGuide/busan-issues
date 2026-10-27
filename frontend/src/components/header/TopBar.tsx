import { AIR_GRADE_COLOR, weatherIcon } from '../../lib/constants'
import { formatClock, formatDateTime } from '../../lib/format'
import type { AirNow, WeatherNow } from '../../types'

interface TopBarProps {
  now: number
  weather: WeatherNow | null
  air: AirNow | null
}

export default function TopBar({ now, weather, air }: TopBarProps) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-panel px-4">
      <span className="relative flex h-2.5 w-2.5 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-danger opacity-75" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-danger" />
      </span>
      <h1 className="text-base font-bold whitespace-nowrap">부산 알리미</h1>

      <div className="ml-auto flex items-center gap-4 text-sm">
        {weather && weather.temperature != null && (
          <span
            className="whitespace-nowrap"
            title={`습도 ${weather.humidity ?? '-'}% · 1시간 강수 ${weather.precipitation_1h ?? 0}mm · 풍속 ${weather.wind_speed ?? '-'}m/s\n${formatClock(weather.observed_at)} 관측 · ${weather.source}`}
          >
            {weatherIcon(weather.precipitation_type, weather.sky)} <strong>{Math.round(weather.temperature)}°C</strong>
            <span className="ml-1 hidden text-muted sm:inline">
              {weather.precipitation_type !== '없음' ? weather.precipitation_type : weather.sky}
            </span>
          </span>
        )}
        {air?.grade && (
          <span
            className="whitespace-nowrap"
            title={`${air.station} 측정소 (${air.distance_km}km) · PM10 ${air.pm10 ?? '-'}㎍/㎥ (${air.pm10_grade ?? '-'}) · PM2.5 ${air.pm25 ?? '-'}㎍/㎥ (${air.pm25_grade ?? '-'})\n${formatClock(air.measured_at)} 측정 · ${air.source}`}
          >
            <span className="hidden text-muted sm:inline">미세먼지 </span>
            <strong style={{ color: AIR_GRADE_COLOR[air.grade] }}>{air.grade}</strong>
          </span>
        )}
        <span className="hidden whitespace-nowrap text-muted lg:inline">{formatDateTime(new Date(now))}</span>
      </div>
    </header>
  )
}
