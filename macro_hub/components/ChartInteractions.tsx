'use client'
import { useEffect } from 'react'
import { enhanceCharts } from '@/lib/chart-interactions'
export default function ChartInteractions() {
  useEffect(() => enhanceCharts(document), [])
  return null
}
