import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export interface Pin {
  name: string
  lat: number
  lon: number
  /** A must-do place of the traveler looking. */
  filled: boolean
}

/** Every place on the list that has coordinates, as pins; the viewer's must-do places filled. */
export function PlaceMap({ pins }: { pins: Pin[] }) {
  const box = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const layer = useRef<L.LayerGroup | null>(null)
  const any = pins.length > 0

  useEffect(() => {
    if (!box.current) return
    const m = L.map(box.current)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors' }).addTo(m)
    map.current = m
    layer.current = L.layerGroup().addTo(m)
    // Without this React's second run of the effect in development finds the container taken.
    return () => { m.remove(); map.current = null }
  }, [any])

  // Where the pins are, apart from which are filled: marking a place must not move the map.
  const spots = pins.map((p) => `${p.lat},${p.lon}`).join(' ')
  useEffect(() => {
    if (spots) map.current?.fitBounds(L.latLngBounds(pins.map((p) => [p.lat, p.lon])), { padding: [24, 24], maxZoom: 14 })
  }, [spots])

  useEffect(() => {
    if (!box.current || !layer.current) return
    const color = getComputedStyle(box.current).getPropertyValue('--pick').trim()
    layer.current.clearLayers()
    for (const p of pins) {
      L.circleMarker([p.lat, p.lon], { radius: 7, weight: 2, color, fillColor: p.filled ? color : '#fff', fillOpacity: 1 })
        .bindTooltip(p.name)
        .addTo(layer.current)
    }
  })

  return any ? <div ref={box} className="map" /> : null
}
