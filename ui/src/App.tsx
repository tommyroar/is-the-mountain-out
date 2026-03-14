import { useState, useEffect, useCallback, useRef } from 'react'
import { Mountain, CloudSun, CheckCircle2, ChevronRight, HardDrive, MousePointer2, Trash2 } from 'lucide-react'

interface Stats {
  labeled: number;
  counts: Record<number, number>;
  labels_path: string;
  total_images: number;
}

interface ImageBatch {
  images: string[];
  total_unlabeled: number;
  total_images: number;
}

interface SelectionBox {
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
}

function App() {
  const [images, setImages] = useState<string[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [selections, setSelections] = useState<Record<string, number>>({})
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [apiBase, setApiBase] = useState<string>(`http://tommys-mac-mini.local:8001`)
  const [imageSize, setImageSize] = useState<number>(250)
  
  // Pinch to zoom state
  const touchStartDist = useRef<number | null>(null)
  const initialImageSize = useRef<number>(250)

  // Trackpad pinch (wheel + ctrl)
  useEffect(() => {
    const handleWheel = (e: WheelEvent) => {
      if (e.ctrlKey) {
        e.preventDefault()
        const zoomSpeed = 2
        setImageSize(prev => {
          const next = prev - e.deltaY * zoomSpeed
          return Math.min(Math.max(next, 100), 800)
        })
      }
    }
    window.addEventListener('wheel', handleWheel, { passive: false })
    return () => window.removeEventListener('wheel', handleWheel)
  }, [])

  // iOS Pinch
  useEffect(() => {
    const handleTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 2) {
        const dist = Math.hypot(
          e.touches[0].pageX - e.touches[1].pageX,
          e.touches[0].pageY - e.touches[1].pageY
        )
        touchStartDist.current = dist
        initialImageSize.current = imageSize
      }
    }

    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches.length === 2 && touchStartDist.current !== null) {
        e.preventDefault()
        const dist = Math.hypot(
          e.touches[0].pageX - e.touches[1].pageX,
          e.touches[0].pageY - e.touches[1].pageY
        )
        const scale = dist / touchStartDist.current
        const next = initialImageSize.current * scale
        setImageSize(Math.min(Math.max(next, 100), 800))
      }
    }

    const handleTouchEnd = () => {
      touchStartDist.current = null
    }

    window.addEventListener('touchstart', handleTouchStart, { passive: false })
    window.addEventListener('touchmove', handleTouchMove, { passive: false })
    window.addEventListener('touchend', handleTouchEnd)
    return () => {
      window.removeEventListener('touchstart', handleTouchStart)
      window.removeEventListener('touchmove', handleTouchMove)
      window.removeEventListener('touchend', handleTouchEnd)
    }
  }, [imageSize])
  
  // Selection box state
  const [selectionBox, setSelectionBox] = useState<SelectionBox | null>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const isDragging = useRef(false)

  const fetchData = useCallback(async (base = apiBase) => {
    setLoading(true)
    try {
      const [imgRes, statsRes] = await Promise.all([
        fetch(`${base}/api/images?batch_size=60`),
        fetch(`${base}/api/stats`)
      ])
      const imgData: ImageBatch = await imgRes.json()
      const statsData: Stats = await statsRes.json()
      
      setImages(imgData.images)
      setStats({ ...statsData, total_images: imgData.total_images })
      setSelections({})
      setSelectedPaths(new Set())
    } catch (err) {
      console.error("Failed to fetch data", err)
    } finally {
      setLoading(false)
    }
  }, [apiBase])

  useEffect(() => {
    const initApp = async () => {
      let currentApiBase = apiBase
      try {
        // If we are on HTTPS (Tailscale Serve), we use relative paths for everything
        if (window.location.protocol === 'https:') {
          currentApiBase = window.location.origin
        } else {
          const configRes = await fetch('config.json')
          if (configRes.ok) {
            const config = await configRes.json()
            currentApiBase = `http://${window.location.hostname}:${config.API_PORT}`
          }
        }
        setApiBase(currentApiBase)
      } catch (err) {
        console.warn("Could not load config, using default", err)
      }
      fetchData(currentApiBase)
    }
    initApp()
  }, [])

  const applyBulkLabel = (val: number | null) => {
    setSelections(prev => {
      const next = { ...prev }
      selectedPaths.forEach(path => {
        if (val === null) {
          delete next[path]
        } else {
          next[path] = val
        }
      })
      return next
    })
    setSelectedPaths(new Set())
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    const payload = {
      labels: images.reduce((acc, path) => {
        acc[path] = selections[path] || 0
        return acc
      }, {} as Record<string, number>)
    }

    try {
      await fetch(`${apiBase}/api/label`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      await fetchData()
    } catch (err) {
      console.error("Submission failed", err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return
    const target = e.target as HTMLElement
    if (target.closest('button') || target.closest('header')) return

    isDragging.current = true
    setSelectionBox({
      startX: e.clientX,
      startY: e.clientY,
      currentX: e.clientX,
      currentY: e.clientY
    })
  }

  const handleMouseMove = (e: MouseEvent) => {
    if (!isDragging.current || !selectionBox) return

    setSelectionBox(prev => prev ? ({
      ...prev,
      currentX: e.clientX,
      currentY: e.clientY
    }) : null)

    const x1 = Math.min(selectionBox.startX, e.clientX)
    const x2 = Math.max(selectionBox.startX, e.clientX)
    const y1 = Math.min(selectionBox.startY, e.clientY)
    const y2 = Math.max(selectionBox.startY, e.clientY)

    const newSelected = new Set<string>()
    const items = gridRef.current?.querySelectorAll('[data-path]')
    items?.forEach(item => {
      const rect = item.getBoundingClientRect()
      const path = item.getAttribute('data-path')
      if (path && !(rect.right < x1 || rect.left > x2 || rect.bottom < y1 || rect.top > y2)) {
        newSelected.add(path)
      }
    })

    setSelectedPaths(newSelected)
  }

  const handleMouseUp = () => {
    isDragging.current = false
    setSelectionBox(null)
  }

  useEffect(() => {
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [selectionBox])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' || e.code === 'Enter') {
        e.preventDefault()
        handleSubmit()
      }
      if (e.key === '1') applyBulkLabel(1)
      if (e.key === '2') applyBulkLabel(2)
      if (e.key === '0' || e.key === 'Backspace') applyBulkLabel(0)
      if (e.key === 'Escape') setSelectedPaths(new Set())
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [images, selections, selectedPaths])

  if (loading && !images.length) {
    return (
      <div className="flex items-center justify-center h-screen bg-black">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-black text-zinc-100 select-none cursor-default font-sans">
      {/* Self-Collapsing Header */}
      <header className="fixed top-0 left-0 w-full z-[300] transition-all duration-500 transform -translate-y-[90%] hover:translate-y-0 group">
        <div className="bg-zinc-900/95 backdrop-blur-2xl border-b border-zinc-800 p-4 shadow-2xl">
          <div className="max-w-[1600px] mx-auto flex items-center justify-between gap-8">
            <div className="flex items-center gap-6">
              <div className="flex flex-col">
                <h1 className="text-xl font-black italic tracking-tighter uppercase flex items-center gap-2">
                  <Mountain className="text-blue-500" size={24} />
                  Mountain Classifier
                </h1>
                <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-widest truncate max-w-[200px]">
                  {stats?.labels_path.split('/').pop()}
                </span>
              </div>

              {stats && (
                <div className="flex gap-4 items-center bg-black/40 px-4 py-2 rounded-xl border border-zinc-800/50">
                  <div className="flex flex-col items-center px-3 border-r border-zinc-800">
                    <span className="text-[9px] text-zinc-500 uppercase font-black">Progress</span>
                    <span className="text-lg font-mono font-bold leading-none">
                      {((stats.labeled / stats.total_images) * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <span className="text-green-500 font-bold text-sm leading-none">{stats.counts[1] || 0}</span>
                      <span className="text-[8px] text-zinc-500 uppercase font-bold mt-1">Full</span>
                    </div>
                    <div className="flex flex-col items-center">
                      <span className="text-orange-500 font-bold text-sm leading-none">{stats.counts[2] || 0}</span>
                      <span className="text-[8px] text-zinc-500 uppercase font-bold mt-1">Part</span>
                    </div>
                    <div className="flex flex-col items-center">
                      <span className="text-red-500 font-bold text-sm leading-none">{stats.counts[0] || 0}</span>
                      <span className="text-[8px] text-zinc-500 uppercase font-bold mt-1">None</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
{/* Actions */}
<div className="flex items-center gap-6">
  <div className="flex items-center gap-3 bg-black/40 px-4 py-2 rounded-xl border border-zinc-800/50">
    <span className="text-[9px] text-zinc-500 uppercase font-black">Size</span>
    <input 
      type="range" 
      min="100" 
      max="800" 
      value={imageSize} 
      onChange={(e) => setImageSize(parseInt(e.target.value))}
      className="w-32 h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
    />
  </div>

  <div className={`flex gap-2 transition-all duration-300 ${selectedPaths.size > 0 ? 'opacity-100 scale-100' : 'opacity-0 scale-95 pointer-events-none'}`}>

                <button onClick={() => applyBulkLabel(1)} className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-lg font-bold text-xs flex items-center gap-2 transition-colors">
                  <Mountain size={14} /> FULL <kbd className="opacity-50 bg-black/20 px-1 rounded text-[10px]">1</kbd>
                </button>
                <button onClick={() => applyBulkLabel(2)} className="bg-orange-600 hover:bg-orange-500 text-white px-4 py-2 rounded-lg font-bold text-xs flex items-center gap-2 transition-colors">
                  <CloudSun size={14} /> PART <kbd className="opacity-50 bg-black/20 px-1 rounded text-[10px]">2</kbd>
                </button>
                <button onClick={() => applyBulkLabel(0)} className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg font-bold text-xs flex items-center gap-2 transition-colors">
                  <Trash2 size={14} /> NONE <kbd className="opacity-50 bg-black/20 px-1 rounded text-[10px]">0</kbd>
                </button>
              </div>
              
              <div className="w-px h-8 bg-zinc-800 mx-2" />

              <button
                onClick={handleSubmit}
                disabled={submitting || images.length === 0}
                className="bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-800 text-white px-6 py-2 rounded-lg font-bold text-sm flex items-center gap-2 shadow-lg transition-all active:scale-95"
              >
                {submitting ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <CheckCircle2 size={18} />}
                SUBMIT BATCH <kbd className="opacity-50 bg-black/20 px-1 rounded text-[10px]">SPACE</kbd>
              </button>
            </div>
          </div>
        </div>
        {/* Visual Cue / Handle / Progress Bar when collapsed */}
        <div className="h-4 w-full flex flex-col items-center justify-start group-hover:opacity-0 transition-opacity">
            <div className="h-1 w-24 bg-zinc-800 rounded-full mt-1.5 opacity-50" />
            {stats && (
              <div className="absolute bottom-0 left-0 w-full h-[2px] bg-white/5">
                <div 
                  className="h-full bg-gradient-to-r from-red-500 via-yellow-500 via-green-500 via-blue-500 to-purple-500 transition-all duration-1000 shadow-[0_0_8px_rgba(255,255,255,0.3)]" 
                  style={{ width: `${(stats.labeled / stats.total_images) * 100}%` }}
                />
              </div>
            )}
        </div>
        </header>


      <main className="p-4 pt-8 max-w-[1900px] mx-auto min-h-screen">
        {images.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[80vh] text-center">
            <CheckCircle2 className="text-green-500 mb-6 animate-bounce" size={120} />
            <h2 className="text-5xl font-black text-zinc-100 uppercase tracking-tighter italic">Dataset Complete</h2>
            <p className="text-zinc-500 mt-4 text-xl font-medium max-w-md leading-relaxed">All images in this directory have been successfully labeled.</p>
          </div>
        ) : (
          <div 
            ref={gridRef}
            onMouseDown={handleMouseDown}
            className="grid gap-3"
            style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${imageSize}px, 1fr))` }}
          >
            {images.map((path) => (
              <div 
                key={path}
                data-path={path}
                className={`group relative bg-zinc-900 rounded-xl overflow-hidden border-4 transition-all duration-150 cursor-pointer ${
                  selectedPaths.has(path) ? 'border-blue-500 scale-[0.98] ring-8 ring-blue-500/20' :
                  selections[path] === 1 ? 'border-green-600/50' :
                  selections[path] === 2 ? 'border-orange-600/50' :
                  selections[path] === 0 ? 'border-red-600/50' :
                  'border-zinc-800 hover:border-zinc-600'
                }`}
              >
                <img
                  src={`${apiBase}/data/${path}`}
                  alt="Webcam"
                  className={`w-full h-auto block transition-opacity duration-300 ${loading ? 'opacity-0' : 'opacity-100'}`}
                  loading="lazy"
                  draggable="false"
                  onDragStart={(e) => e.preventDefault()}
                />
                
                <div className="absolute bottom-2 left-2 flex gap-1">
                  {selections[path] === 1 && <div className="bg-green-600 text-white p-1 rounded-md shadow-lg"><Mountain size={14} /></div>}
                  {selections[path] === 2 && <div className="bg-orange-600 text-white p-1 rounded-md shadow-lg"><CloudSun size={14} /></div>}
                  {selections[path] === 0 && <div className="bg-red-600 text-white p-1 rounded-md shadow-lg font-black text-[10px] w-5 h-5 flex items-center justify-center">X</div>}
                </div>

                {selectedPaths.has(path) && (
                  <div className="absolute top-2 right-2 bg-blue-500 text-zinc-950 p-1 rounded-full shadow-2xl scale-110">
                    <CheckCircle2 size={16} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>

      {selectionBox && (
        <div 
          className="fixed border border-blue-400 bg-blue-500/20 pointer-events-none z-[400] rounded-sm"
          style={{
            left: Math.min(selectionBox.startX, selectionBox.currentX),
            top: Math.min(selectionBox.startY, selectionBox.currentY),
            width: Math.abs(selectionBox.startX - selectionBox.currentX),
            height: Math.abs(selectionBox.startY - selectionBox.currentY),
          }}
        />
      )}
      
      {/* Selection Hint Overlay */}
      <div className="fixed bottom-4 right-6 text-zinc-700 font-black text-[10px] uppercase tracking-widest pointer-events-none">
        {selectedPaths.size > 0 ? `${selectedPaths.size} Selected` : 'Drag to Multi-Select'}
      </div>
    </div>
  )
}

export default App
